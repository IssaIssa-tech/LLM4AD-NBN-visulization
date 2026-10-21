from __future__ import annotations

import contextlib
import json
import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

import os

from visual_platform.config import BASE_DIR

# 环境变量覆盖：把平台数据库指向一块更快的本地工作副本（例如 /tmp），
# 以避开网络/虚拟文件系统上不稳定的 I/O；写回持久位置的同步由调用方负责。
DB_PATH = Path(os.environ.get("VISUAL_PLATFORM_DB", str(BASE_DIR / "llm4ad_platform.sqlite3")))

_schema_lock = threading.Lock()
_schema_initialized = False


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def json_loads(payload: Any, fallback: Any) -> Any:
    if payload in (None, ""):
        return fallback
    if isinstance(payload, (dict, list)):
        return payload
    try:
        return json.loads(str(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _connect_raw() -> sqlite3.Connection:
    # Graph-build result writes can hold the write lock well beyond 10s on
    # /mnt/d, which used to kill concurrent readers with "database is locked".
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def _stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _legacy_graph_input_digest(row: sqlite3.Row) -> str:
    payload = {
        "artifactType": "graph",
        "artifactRole": str(row["variant"] or "full"),
        "distanceMetric": str(row["metric"] or "").strip().lower(),
        "graphOptions": {
            "maxNodes": int(row["max_nodes"] or 0),
            "variant": str(row["variant"] or "full"),
        },
        "revisionId": str(row["revision_id"]),
        "sampleRevision": int(row["sample_revision"] or 0),
        "schemaVersion": 1,
    }
    return hashlib.sha256(_stable_json_dumps(payload).encode("utf-8")).hexdigest()


def _migrate_legacy_graph_artifacts(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "graph_artifacts"):
        return

    rows = conn.execute("SELECT * FROM graph_artifacts").fetchall()
    for row in rows:
        variant = str(row["variant"] or "full")
        revision_id = str(row["revision_id"])
        metadata = {
            "summary": json_loads(row["summary_json"], {}),
            "metric": str(row["metric"] or "").strip().lower(),
            "maxNodes": int(row["max_nodes"] or 0),
            "sampleRevision": int(row["sample_revision"] or 0),
            "variant": variant,
            "legacyBuiltAt": row["built_at"],
            "migratedFrom": "graph_artifacts",
        }
        created_by_job_id = f"graph-build:{revision_id}" if variant == "full" else f"graph-build:{revision_id}:{variant}"
        input_digest = _legacy_graph_input_digest(row)
        conn.execute(
            """
            INSERT INTO artifacts (
                artifact_id,
                revision_id,
                artifact_type,
                artifact_role,
                format,
                storage_uri,
                content_digest,
                input_digest,
                status,
                metadata_json,
                error_message,
                created_by_job_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
            ON CONFLICT(revision_id, artifact_type, artifact_role, input_digest) DO UPDATE SET
                storage_uri = excluded.storage_uri,
                status = excluded.status,
                metadata_json = excluded.metadata_json,
                error_message = excluded.error_message,
                created_by_job_id = COALESCE(excluded.created_by_job_id, artifacts.created_by_job_id),
                updated_at = excluded.updated_at
            """,
            (
                str(row["artifact_id"]),
                revision_id,
                "graph",
                variant,
                "json",
                str(row["path"] or ""),
                None,
                input_digest,
                str(row["status"] or "pending"),
                json_dumps(metadata),
                str(row["error"] or "").strip() or None,
                created_by_job_id,
                row["built_at"],
                row["updated_at"],
            ),
        )


# New-schema DDL for the workspace-scoped individual pool. Kept in one place so the
# fresh-DB CREATE and the migration rebuild stay byte-for-byte identical.
def _individuals_table_ddl(table_name: str) -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id TEXT PRIMARY KEY,
            revision_id TEXT,
            workspace_id TEXT,
            parent_id TEXT,
            sample_order INTEGER,
            generation INTEGER,
            score REAL,
            code TEXT,
            algorithm_summary TEXT,
            source_kind TEXT,
            is_expert BOOLEAN DEFAULT 0,
            raw_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE SET NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
        )
    """


def _migrate_individuals_to_workspace_pool() -> None:
    """Rebuild the individuals table so a solution survives deletion of its origin
    revision (ON DELETE SET NULL) and is scoped to a workspace instead of being
    hard-cascaded by a single revision. Idempotent: gated on the workspace_id column.
    """
    conn = _connect_raw()
    conn.isolation_level = None  # autocommit so PRAGMA foreign_keys toggles take effect
    try:
        if not _table_exists(conn, "individuals"):
            return  # fresh DB: the main block creates the new schema directly
        if "workspace_id" in _table_columns(conn, "individuals"):
            return  # already migrated
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")
        try:
            conn.execute(_individuals_table_ddl("individuals_new"))
            conn.execute(
                """
                INSERT INTO individuals_new
                    (id, revision_id, workspace_id, parent_id, sample_order, generation,
                     score, code, algorithm_summary, source_kind, is_expert, raw_payload, created_at)
                SELECT
                    i.id, i.revision_id,
                    (SELECT r.workspace_id FROM revisions r WHERE r.revision_id = i.revision_id),
                    i.parent_id, i.sample_order, i.generation, i.score, i.code,
                    i.algorithm_summary, i.source_kind, i.is_expert, i.raw_payload, i.created_at
                FROM individuals i
                """
            )
            conn.execute("DROP TABLE individuals")
            conn.execute("ALTER TABLE individuals_new RENAME TO individuals")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


def _backfill_revision_nodes(conn: sqlite3.Connection) -> None:
    """Populate the revision_nodes membership table once, so existing versions keep
    every node currently shown in their (possibly merged) graph even after older
    source revisions are deleted. Runs a single time, guarded by app_state.
    """
    row = conn.execute(
        "SELECT value FROM app_state WHERE key = 'revision_nodes_backfilled'"
    ).fetchone()
    if row is not None and str(row["value"]) == "1":
        return

    # 1) Self-membership: every individual belongs to its origin revision.
    conn.execute(
        "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) "
        "SELECT revision_id, id FROM individuals WHERE revision_id IS NOT NULL"
    )

    # 2) Cross-membership: parse each revision's built graph and record every node
    #    that maps to a known individual as a member of that revision.
    try:
        from visual_platform.config import RUNS_DIR

        existing_ids = {
            str(r["id"]) for r in conn.execute("SELECT id FROM individuals").fetchall()
        }
        revision_ids = [
            str(r["revision_id"])
            for r in conn.execute("SELECT revision_id FROM revisions").fetchall()
        ]
        for revision_id in revision_ids:
            graph_path = Path(RUNS_DIR) / revision_id / "graph_full.json"
            if not graph_path.exists():
                continue
            try:
                data = json.loads(graph_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            nodes = data.get("nodes") if isinstance(data, dict) else None
            if not isinstance(nodes, list):
                continue
            pairs = []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = str(node.get("id") or "").strip()
                if node_id and node_id in existing_ids:
                    pairs.append((revision_id, node_id))
            if pairs:
                conn.executemany(
                    "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) VALUES (?, ?)",
                    pairs,
                )
    except Exception:
        # Best-effort: self-membership already covers correctness for future builds.
        pass

    conn.execute(
        "INSERT OR REPLACE INTO app_state (key, value) VALUES ('revision_nodes_backfilled', '1')"
    )


def init_db_schema() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    with _schema_lock:
        if _schema_initialized:
            return
        _migrate_individuals_to_workspace_pool()
        with _connect_raw() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    current_revision_id TEXT,
                    sort_index INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            ensure_column(conn, "workspaces", "description", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    lifecycle_status TEXT DEFAULT 'idle',
                    graph_status TEXT DEFAULT 'none',
                    config TEXT,
                    error TEXT,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    latest_job_id TEXT,
                    sample_revision INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS individuals (
                    id TEXT PRIMARY KEY,
                    revision_id TEXT,
                    workspace_id TEXT,
                    parent_id TEXT,
                    sample_order INTEGER,
                    generation INTEGER,
                    score REAL,
                    code TEXT,
                    algorithm_summary TEXT,
                    source_kind TEXT,
                    is_expert BOOLEAN DEFAULT 0,
                    raw_payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE SET NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    stage_label TEXT,
                    current INTEGER,
                    total INTEGER,
                    percent REAL,
                    message TEXT,
                    error TEXT,
                    payload_json TEXT,
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    level TEXT DEFAULT 'info',
                    status TEXT,
                    stage TEXT,
                    stage_label TEXT,
                    current INTEGER,
                    total INTEGER,
                    percent REAL,
                    message TEXT,
                    error TEXT,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    artifact_role TEXT NOT NULL,
                    format TEXT NOT NULL,
                    storage_uri TEXT NOT NULL DEFAULT '',
                    content_digest TEXT,
                    input_digest TEXT,
                    status TEXT NOT NULL,
                    metadata_json TEXT,
                    error_message TEXT,
                    created_by_job_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    metric TEXT,
                    max_nodes INTEGER,
                    sample_revision INTEGER DEFAULT 0,
                    path TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    summary_json TEXT,
                    built_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS revision_nodes (
                    revision_id TEXT NOT NULL,
                    individual_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (revision_id, individual_id),
                    FOREIGN KEY(revision_id) REFERENCES revisions(revision_id) ON DELETE CASCADE,
                    FOREIGN KEY(individual_id) REFERENCES individuals(id) ON DELETE CASCADE
                )
                """
            )

            conn.execute("CREATE INDEX IF NOT EXISTS idx_individuals_workspace_id ON individuals(workspace_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_revision_nodes_individual ON revision_nodes(individual_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_individuals_revision_id ON individuals(revision_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_individuals_revision_score ON individuals(revision_id, score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_individuals_parent_id ON individuals(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_individuals_run_order ON individuals(revision_id, sample_order)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_active ON workspaces(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_run_type ON jobs(revision_id, job_type, updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_run_time ON job_events(revision_id, created_at, event_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job_seq ON job_events(job_id, seq)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_revision_type ON artifacts(revision_id, artifact_type, artifact_role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_revision_status ON artifacts(revision_id, status)")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_artifacts_revision_role_input "
                "ON artifacts(revision_id, artifact_type, artifact_role, input_digest)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_artifacts_run_variant ON graph_artifacts(revision_id, variant, max_nodes)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_artifacts_revision_id ON graph_artifacts(revision_id)")
            # User-supplied display name for a revision (optional). NULL/empty
            # falls back to showing the raw revision_id in the UI.
            ensure_column(conn, "revisions", "display_name", "TEXT")
            _migrate_legacy_graph_artifacts(conn)
            _backfill_revision_nodes(conn)
        # sqlite3 的 `with conn:` 只负责提交/回滚事务，**不会**关闭连接；
        # 这里显式关闭，避免进程初始化时漏一个文件描述符。
        conn.close()
        _schema_initialized = True


@contextlib.contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """借出一个数据库连接，退出时必定关闭。

    注意 sqlite3 的 `with conn:` 只提交/回滚事务、**不关闭**连接，因此先前每个
    `with get_connection() as conn:` 都会漏掉一个文件描述符（线程化 Flask +
    Celery 下会逐步耗尽）。这里保留原有的 commit/rollback 语义，并在 finally 中
    关闭连接。
    """
    init_db_schema()
    conn = _connect_raw()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
