from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

from hashtag_robotics.models import (
    ApprovalRecord,
    ApprovalStatus,
    AuditEvent,
    JobRecord,
    JobState,
    ResourceLease,
    ResourceRequest,
    utc_now,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class RepositoryError(RuntimeError):
    pass


class ResourceBusyError(RepositoryError):
    def __init__(self, resource_id: str, owner_job_id: str) -> None:
        super().__init__(f"Resource '{resource_id}' is owned by job '{owner_job_id}'")
        self.resource_id = resource_id
        self.owner_job_id = owner_job_id


class Repository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, id)
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS leases (
                    resource_id TEXT NOT NULL,
                    owner_job_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (resource_id, owner_job_id)
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS flags (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
                CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_approvals_job ON approvals(job_id);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_events(timestamp DESC);
                """
            )

    def upsert_entity(self, kind: str, entity: BaseModel) -> None:
        entity_id = str(entity.id)
        now = utc_now().isoformat()
        payload = entity.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entities(kind, id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(kind, id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (kind, entity_id, payload, now, now),
            )

    def get_entity(self, kind: str, entity_id: str, model: type[ModelT]) -> ModelT | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM entities WHERE kind = ? AND id = ?",
                (kind, entity_id),
            ).fetchone()
        return model.model_validate_json(row["payload"]) if row else None

    def list_entities(self, kind: str, model: type[ModelT]) -> list[ModelT]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM entities WHERE kind = ? ORDER BY updated_at DESC",
                (kind,),
            ).fetchall()
        return [model.model_validate_json(row["payload"]) for row in rows]

    def delete_entity(self, kind: str, entity_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM entities WHERE kind = ? AND id = ?",
                (kind, entity_id),
            )
            return cursor.rowcount > 0

    def get_flag(self, name: str) -> str | None:
        """Read a latched control-plane flag; it survives restarts by design."""
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM flags WHERE name = ?",
                (name,),
            ).fetchone()
        return str(row["value"]) if row else None

    def set_flag(self, name: str, value: str | None) -> None:
        with self._lock, self._connect() as connection:
            if value is None:
                connection.execute("DELETE FROM flags WHERE name = ?", (name,))
                return
            connection.execute(
                """
                INSERT INTO flags(name, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (name, value, utc_now().isoformat()),
            )

    def create_job(self, job: JobRecord) -> JobRecord:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs(id, state, updated_at, payload) VALUES (?, ?, ?, ?)",
                (job.id, job.state.value, job.updated_at.isoformat(), job.model_dump_json()),
            )
        return job

    def update_job(self, job: JobRecord) -> JobRecord:
        job.updated_at = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET state = ?, updated_at = ?, payload = ?
                WHERE id = ?
                """,
                (job.state.value, job.updated_at.isoformat(), job.model_dump_json(), job.id),
            )
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return JobRecord.model_validate_json(row["payload"]) if row else None

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM jobs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [JobRecord.model_validate_json(row["payload"]) for row in rows]

    def recover_incomplete_jobs(self) -> list[JobRecord]:
        incomplete = {
            JobState.CREATED.value,
            JobState.VALIDATING.value,
            JobState.QUEUED.value,
            JobState.STARTING.value,
            JobState.RUNNING.value,
            JobState.STOPPING.value,
        }
        recovered: list[JobRecord] = []
        for job in self.list_jobs(limit=10_000):
            if job.state.value in incomplete:
                job.state = JobState.INTERRUPTED
                job.error_code = "process_restart"
                job.error_message = "The application restarted before this job completed."
                job.message = "Interrupted safely after application restart"
                self.update_job(job)
                self.release_leases(job.id)
                recovered.append(job)
        return recovered

    def lease_owner(self, resource_id: str) -> str | None:
        """Who currently holds this resource, ignoring leases that have expired.

        Expired rows are only swept when someone tries to acquire, so a caller
        that merely asks must filter them out or it will report a device as busy
        long after its holder is gone.
        """
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT owner_job_id FROM leases WHERE resource_id = ? AND expires_at > ? "
                "ORDER BY expires_at DESC LIMIT 1",
                (resource_id, utc_now().isoformat()),
            ).fetchone()
        return str(row["owner_job_id"]) if row else None

    def acquire_leases(
        self,
        job_id: str,
        resources: Iterable[ResourceRequest],
        ttl_seconds: int = 30,
    ) -> list[ResourceLease]:
        now = utc_now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        requests = list(resources)
        leases: list[ResourceLease] = []
        if not requests:
            return leases

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM leases WHERE expires_at <= ?",
                (now.isoformat(),),
            )
            for request in requests:
                rows = connection.execute(
                    "SELECT owner_job_id, mode FROM leases WHERE resource_id = ?",
                    (request.resource_id,),
                ).fetchall()
                for row in rows:
                    same_owner = row["owner_job_id"] == job_id
                    shared_compatible = (
                        request.mode == "shared_read" and row["mode"] == "shared_read"
                    )
                    if not same_owner and not shared_compatible:
                        connection.rollback()
                        raise ResourceBusyError(request.resource_id, row["owner_job_id"])

                lease = ResourceLease(
                    resource_id=request.resource_id,
                    resource_type=request.resource_type,
                    owner_job_id=job_id,
                    mode=request.mode,
                    acquired_at=now,
                    heartbeat_at=now,
                    expires_at=expires_at,
                )
                connection.execute(
                    """
                    INSERT INTO leases(
                        resource_id, owner_job_id, resource_type, mode, expires_at, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(resource_id, owner_job_id) DO UPDATE SET
                        mode = excluded.mode,
                        expires_at = excluded.expires_at,
                        payload = excluded.payload
                    """,
                    (
                        lease.resource_id,
                        lease.owner_job_id,
                        lease.resource_type,
                        lease.mode,
                        lease.expires_at.isoformat(),
                        lease.model_dump_json(),
                    ),
                )
                leases.append(lease)
            connection.commit()
        return leases

    def heartbeat_leases(self, job_id: str, ttl_seconds: int = 30) -> None:
        now = utc_now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM leases WHERE owner_job_id = ?",
                (job_id,),
            ).fetchall()
            for row in rows:
                lease = ResourceLease.model_validate_json(row["payload"])
                lease.heartbeat_at = now
                lease.expires_at = expires_at
                connection.execute(
                    """
                    UPDATE leases
                    SET expires_at = ?, payload = ?
                    WHERE resource_id = ? AND owner_job_id = ?
                    """,
                    (
                        expires_at.isoformat(),
                        lease.model_dump_json(),
                        lease.resource_id,
                        job_id,
                    ),
                )

    def release_leases(self, job_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM leases WHERE owner_job_id = ?", (job_id,))

    def list_leases(self) -> list[ResourceLease]:
        now = utc_now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM leases WHERE expires_at <= ?", (now,))
            rows = connection.execute("SELECT payload FROM leases ORDER BY resource_id").fetchall()
        return [ResourceLease.model_validate_json(row["payload"]) for row in rows]

    def create_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals(id, job_id, status, expires_at, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    approval.id,
                    approval.job_id,
                    approval.status.value,
                    approval.expires_at.isoformat(),
                    approval.model_dump_json(),
                ),
            )
        return approval

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM approvals WHERE id = ?",
                (approval_id,),
            ).fetchone()
        return ApprovalRecord.model_validate_json(row["payload"]) if row else None

    def update_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, expires_at = ?, payload = ?
                WHERE id = ?
                """,
                (
                    approval.status.value,
                    approval.expires_at.isoformat(),
                    approval.model_dump_json(),
                    approval.id,
                ),
            )
        return approval

    def expire_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        approval.status = ApprovalStatus.EXPIRED
        return self.update_approval(approval)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events(id, timestamp, correlation_id, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.timestamp.isoformat(),
                    event.correlation_id,
                    event.model_dump_json(),
                ),
            )
        return event

    def list_audit(self, limit: int = 200) -> list[AuditEvent]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM audit_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [AuditEvent.model_validate_json(row["payload"]) for row in rows]
