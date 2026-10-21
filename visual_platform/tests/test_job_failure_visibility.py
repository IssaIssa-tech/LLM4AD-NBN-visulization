"""worker 侧失败必须在页面上可见。

覆盖两条兜底路径：
1. 读路径按心跳把僵死的活动任务标记失败（worker 没起 / worker 中途死掉）；
2. Celery task_failure 信号按 task id 把 job 标记失败（服务层没兜住的异常）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from visual_platform.repositories import revision_repository
from visual_platform.runtime import database
from visual_platform.services import job_service
from visual_platform.services import job_query_service
from visual_platform.services import workspace_service


class JobFailureVisibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="vp_job_visibility_"))
        self._saved_db_path = database.DB_PATH
        self._saved_schema_initialized = database._schema_initialized
        database.DB_PATH = self.tmp / "platform.sqlite3"
        database._schema_initialized = False
        # jobs 表对 revision 有外键，先造一个真实存在的 revision。
        self.workspace_id = workspace_service.create_workspace("job-visibility-test")
        self.revision_id = f"rev-{uuid4()}"
        revision_repository.upsert_revision(
            self.revision_id,
            workspace_id=self.workspace_id,
            mode="history_import",
            lifecycle_status="ready",
        )

    def tearDown(self) -> None:
        database._schema_initialized = self._saved_schema_initialized
        database.DB_PATH = self._saved_db_path
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_job(
        self,
        *,
        status: str = "queued",
        age_seconds: float = 0,
        payload: dict | None = None,
        job_type: str = "history_import",
        message: str = "等待 worker 接手",
    ) -> dict:
        job_id = f"job-{uuid4()}"
        job_service.update_job(
            job_id,
            self.revision_id,
            job_type,
            status=status,
            message=message,
            payload=payload or {},
        )
        if age_seconds:
            stale_ts = (datetime.now() - timedelta(seconds=age_seconds)).isoformat(timespec="seconds")
            with database.get_connection() as conn:
                conn.execute(
                    "UPDATE jobs SET created_at = ?, updated_at = ?, started_at = ? WHERE job_id = ?",
                    (stale_ts, stale_ts, stale_ts, job_id),
                )
        job = job_service.get_job(job_id)
        assert job is not None
        return job

    # ---- 读路径兜底 -----------------------------------------------------

    def test_stale_queued_job_is_marked_failed(self) -> None:
        """worker 没起：排队超时的任务必须失败，并说清是"没有 worker 接手"。"""
        job = self._make_job(status="queued", age_seconds=job_service.STALE_JOB_SECONDS * 2)

        reconciled = job_service.reconcile_stale_job(job)

        self.assertIsNotNone(reconciled)
        assert reconciled is not None
        self.assertEqual(reconciled["status"], "failed")
        self.assertIn("worker", str(reconciled.get("error") or ""))
        self.assertIn("排队", str(reconciled.get("message") or ""))
        # 落库了，不只是内存里改了一下
        persisted = job_service.get_job(str(job["job_id"]))
        assert persisted is not None
        self.assertEqual(persisted["status"], "failed")

    def test_stale_running_job_is_marked_failed(self) -> None:
        """worker 中途死掉：running 但心跳停了，同样要失败。"""
        job = self._make_job(status="running", age_seconds=job_service.STALE_JOB_SECONDS * 2)

        reconciled = job_service.reconcile_stale_job(job)

        assert reconciled is not None
        self.assertEqual(reconciled["status"], "failed")
        self.assertIn("worker", str(reconciled.get("error") or ""))

    def test_fresh_active_job_is_untouched(self) -> None:
        job = self._make_job(status="running", age_seconds=5)

        reconciled = job_service.reconcile_stale_job(job)

        assert reconciled is not None
        self.assertEqual(reconciled["status"], "running")
        self.assertIsNone(reconciled.get("error"))

    def test_terminal_job_is_untouched(self) -> None:
        job = self._make_job(status="succeeded", age_seconds=job_service.STALE_JOB_SECONDS * 10)

        reconciled = job_service.reconcile_stale_job(job)

        assert reconciled is not None
        self.assertEqual(reconciled["status"], "succeeded")

    def test_list_recent_jobs_reconciles(self) -> None:
        """工作台读 revision 的那条路径也要能看见失败。"""
        self._make_job(status="queued", age_seconds=job_service.STALE_JOB_SECONDS * 2)

        jobs = job_query_service.list_recent_jobs_for_revision(self.revision_id)

        self.assertEqual([job["status"] for job in jobs], ["failed"])

    # ---- runner 还活着时不能误判 ----------------------------------------

    def test_live_runner_process_is_not_marked_stale(self) -> None:
        """EoH / 区域搜索这类长任务：job 行不更新，但 runner 进程还活着就不能判失败。

        实测一个跑了 610 秒的提示词生成任务，job 事件只有开始那 6 条；只按时间戳
        判会在它还差 10 秒跑完时误标失败。
        """
        job = self._make_job(
            status="running",
            age_seconds=job_service.STALE_JOB_SECONDS * 3,
            payload={"runtime": {"pid": os.getpid()}},
            job_type="revision_generation",
        )

        reconciled = job_service.reconcile_stale_job(job)

        assert reconciled is not None
        self.assertEqual(reconciled["status"], "running")

    def test_dead_runner_process_is_marked_stale(self) -> None:
        """runner 进程没了（被 kill / OOM）仍然要判失败。"""
        reaped = subprocess.Popen([sys.executable, "-c", "pass"])
        reaped.wait()
        job = self._make_job(
            status="running",
            age_seconds=job_service.STALE_JOB_SECONDS * 3,
            payload={"runtime": {"pid": reaped.pid}},
            job_type="revision_generation",
        )

        reconciled = job_service.reconcile_stale_job(job)

        assert reconciled is not None
        self.assertEqual(reconciled["status"], "failed")

    # ---- task_failure 兜底 ---------------------------------------------

    def test_mark_job_failed_by_task_id(self) -> None:
        job = self._make_job(status="running", payload={"taskId": "11111111-2222-3333-4444-555555555555"})

        handled = job_service.mark_job_failed_by_task_id(
            "11111111-2222-3333-4444-555555555555", RuntimeError("boom")
        )

        self.assertTrue(handled)
        persisted = job_service.get_job(str(job["job_id"]))
        assert persisted is not None
        self.assertEqual(persisted["status"], "failed")
        self.assertIn("RuntimeError: boom", str(persisted.get("error") or ""))

    def test_mark_job_failed_keeps_service_level_reason(self) -> None:
        """服务层已经写好失败原因时，兜底不能覆盖它。"""
        job = self._make_job(
            status="failed",
            payload={"taskId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
            message="更具体的失败原因",
        )

        handled = job_service.mark_job_failed_by_task_id(
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", RuntimeError("late signal")
        )

        self.assertFalse(handled)
        persisted = job_service.get_job(str(job["job_id"]))
        assert persisted is not None
        self.assertEqual(persisted["message"], "更具体的失败原因")

    def test_unknown_task_id_is_noop(self) -> None:
        self.assertFalse(job_service.mark_job_failed_by_task_id("no-such-task-id", RuntimeError("x")))


if __name__ == "__main__":
    unittest.main()
