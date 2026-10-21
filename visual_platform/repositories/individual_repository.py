from __future__ import annotations

from typing import Any, List

from visual_platform.repositories.db_support import get_connection, json_dumps, json_loads

def next_sample_order(revision_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(sample_order), 0) + 1 AS next_order FROM individuals WHERE revision_id = ?",
            (revision_id,),
        ).fetchone()
        return int(row["next_order"]) if row else 1


def _workspace_id_for_revision(conn: Any, revision_id: str) -> str | None:
    row = conn.execute(
        "SELECT workspace_id FROM revisions WHERE revision_id = ?", (revision_id,)
    ).fetchone()
    return str(row["workspace_id"]) if row and row["workspace_id"] is not None else None


def insert_individual(individual: dict[str, Any]) -> None:
    parent_id = individual.get("parent_id")
    if individual.get("source_kind") == "external_expert" or individual.get("origin_kind") == "external_expert":
        parent_id = None

    revision_id = individual["revision_id"]
    with get_connection() as conn:
        workspace_id = individual.get("workspace_id") or _workspace_id_for_revision(conn, revision_id)
        existed = conn.execute("SELECT 1 FROM individuals WHERE id = ?", (individual["id"],)).fetchone() is not None
        conn.execute(
            """
            INSERT OR REPLACE INTO individuals
            (id, revision_id, workspace_id, parent_id, sample_order, generation, score, code, algorithm_summary, source_kind, is_expert, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                individual["id"],
                revision_id,
                workspace_id,
                parent_id,
                individual.get("sample_order", 0),
                individual.get("generation", 0),
                individual.get("score"),
                individual.get("function", individual.get("code", "")),
                individual.get("algorithm", individual.get("algorithm_summary", "")),
                individual.get("source_kind", ""),
                1 if individual.get("source_kind") == "external_expert" else 0,
                json_dumps(individual),
            ),
        )
        # Self-membership: the individual is part of its origin revision's graph.
        conn.execute(
            "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) VALUES (?, ?)",
            (revision_id, individual["id"]),
        )
        if not existed:
            conn.execute("UPDATE revisions SET sample_revision = sample_revision + 1 WHERE revision_id = ?", (revision_id,))


def insert_individuals_bulk(individuals: list[dict[str, Any]]) -> None:
    if not individuals:
        return

    records = []
    membership = []
    revision_delta: dict[str, int] = {}
    workspace_cache: dict[str, str | None] = {}
    with get_connection() as conn:
        for individual in individuals:
            parent_id = individual.get("parent_id")
            if individual.get("source_kind") == "external_expert" or individual.get("origin_kind") == "external_expert":
                parent_id = None
            revision_id = individual["revision_id"]
            if revision_id not in workspace_cache:
                workspace_cache[revision_id] = _workspace_id_for_revision(conn, revision_id)
            workspace_id = individual.get("workspace_id") or workspace_cache[revision_id]
            existed = conn.execute("SELECT 1 FROM individuals WHERE id = ?", (individual["id"],)).fetchone() is not None
            if not existed:
                revision_delta[revision_id] = revision_delta.get(revision_id, 0) + 1
            membership.append((revision_id, individual["id"]))
            records.append(
                (
                    individual["id"],
                    revision_id,
                    workspace_id,
                    parent_id,
                    individual.get("sample_order", 0),
                    individual.get("generation", 0),
                    individual.get("score"),
                    individual.get("function", individual.get("code", "")),
                    individual.get("algorithm", individual.get("algorithm_summary", "")),
                    individual.get("source_kind", ""),
                    1 if individual.get("source_kind") == "external_expert" else 0,
                    json_dumps(individual),
                )
            )
        conn.executemany(
            """
            INSERT OR REPLACE INTO individuals
            (id, revision_id, workspace_id, parent_id, sample_order, generation, score, code, algorithm_summary, source_kind, is_expert, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) VALUES (?, ?)",
            membership,
        )
        for rev_id, delta in revision_delta.items():
            conn.execute("UPDATE revisions SET sample_revision = sample_revision + ? WHERE revision_id = ?", (delta, rev_id))


def add_revision_members(revision_id: str, individual_ids: list[str]) -> None:
    """Record that the given individuals are members of a revision's graph.

    Called at graph-build time so merged-in ancestor nodes become first-class
    members of this revision and survive deletion of their origin revision.
    """
    revision_id = str(revision_id or "").strip()
    pairs = [(revision_id, str(node_id)) for node_id in individual_ids if node_id]
    if not revision_id or not pairs:
        return
    with get_connection() as conn:
        # Only record ids that actually exist in the individual pool. Graph node ids
        # can include synthetic summary/cluster ids with no individual row; a plain
        # INSERT would raise a foreign-key error (OR IGNORE does not suppress FK
        # violations), so drive the insert from a SELECT that skips missing ids.
        conn.executemany(
            "INSERT OR IGNORE INTO revision_nodes (revision_id, individual_id) "
            "SELECT ?, id FROM individuals WHERE id = ?",
            pairs,
        )


def list_member_individuals(revision_id: str) -> list[dict[str, Any]]:
    """Return every individual that is a member of this revision's graph (self +
    merged ancestors), independent of whether their origin revision still exists.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT i.* FROM individuals i
            JOIN revision_nodes rn ON rn.individual_id = i.id
            WHERE rn.revision_id = ?
            ORDER BY i.sample_order ASC
            """,
            (revision_id,),
        ).fetchall()
        return [json_loads(row["raw_payload"], {}) for row in rows]


def count_revision_members(revision_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM revision_nodes WHERE revision_id = ?",
            (revision_id,),
        ).fetchone()
        return int(row["cnt"]) if row and row["cnt"] is not None else 0


def count_unique_individuals(revision_id: str) -> int:
    """Count individuals that belong ONLY to this revision (no other surviving
    revision references them). These are the solutions that deletion would
    permanently destroy.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM revision_nodes rn
            WHERE rn.revision_id = ?
              AND rn.individual_id NOT IN (
                  SELECT individual_id FROM revision_nodes WHERE revision_id <> ?
              )
            """,
            (revision_id, revision_id),
        ).fetchone()
        return int(row["cnt"]) if row and row["cnt"] is not None else 0


def gc_orphan_individuals() -> int:
    """Delete individuals no longer referenced by any revision (reference count 0).

    Run after a revision is deleted: individuals still referenced by a surviving
    revision keep a membership row and are preserved.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM individuals WHERE id NOT IN (SELECT individual_id FROM revision_nodes)"
        )
        return int(cursor.rowcount or 0)

def count_expert_individuals(revision_id: str) -> int:
    """Count external-expert individuals stored under a revision.

    Used by the delete guard so an expert-import revision (whose only copy of a
    hand-injected expert solution lives here) is not silently cascade-deleted.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM individuals WHERE revision_id = ? AND is_expert = 1",
            (revision_id,),
        ).fetchone()
        return int(row["cnt"]) if row and row["cnt"] is not None else 0

def get_individuals_by_ids(ids: List[str]) -> List[dict[str, Any]]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM individuals WHERE id IN ({placeholders})", tuple(ids)).fetchall()
        result = []
        for row in rows:
            payload = json_loads(row["raw_payload"], {})
            result.append(payload)
        return result

def list_individuals_for_revision(revision_id: str, *, source_kind: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    query = "SELECT * FROM individuals WHERE revision_id = ?"
    params: list[Any] = [revision_id]
    if source_kind:
        query += " AND source_kind = ?"
        params.append(source_kind)
    query += " ORDER BY sample_order ASC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    
    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        result = []
        for row in rows:
            payload = json_loads(row["raw_payload"], {})
            result.append(payload)
        return result

def get_revision_metrics(revision_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 
                COUNT(*) as sample_count,
                MAX(score) as best_score,
                (SELECT sample_order FROM individuals WHERE revision_id = ? ORDER BY score DESC LIMIT 1) as best_sample_order
            FROM individuals 
            WHERE revision_id = ?
            """,
            (revision_id, revision_id)
        ).fetchone()
        
        sample_count = int(row["sample_count"]) if row and row["sample_count"] is not None else 0
        best_score = float(row["best_score"]) if row and row["best_score"] is not None else None
        best_sample_order = int(row["best_sample_order"]) if row and row["best_sample_order"] is not None else None

        return {
            "sample_count": sample_count,
            "best_score": best_score,
            "best_sample_order": best_sample_order,
            "has_end_marker": False, # no longer use file markers
        }
