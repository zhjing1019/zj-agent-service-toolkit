"""Agent 长任务运行记录（与 LangGraph checkpoint_thread_id 对齐）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.models import AgentTaskRun


class TaskRunRepository:
    @staticmethod
    def upsert_start(
        db: Session,
        checkpoint_thread_id: str,
        session_id: str | None,
        task_preview: str,
    ) -> None:
        row = (
            db.query(AgentTaskRun)
            .filter(AgentTaskRun.checkpoint_thread_id == checkpoint_thread_id)
            .first()
        )
        if row:
            row.session_id = session_id
            row.status = "running"
            row.task_preview = task_preview[:2000]
            row.error_message = None
            row.update_time = datetime.now()
        else:
            db.add(
                AgentTaskRun(
                    checkpoint_thread_id=checkpoint_thread_id,
                    session_id=session_id,
                    status="running",
                    task_preview=task_preview[:2000],
                )
            )
        db.commit()

    @staticmethod
    def mark_completed(
        db: Session,
        checkpoint_thread_id: str,
        result_preview: str,
    ) -> None:
        row = (
            db.query(AgentTaskRun)
            .filter(AgentTaskRun.checkpoint_thread_id == checkpoint_thread_id)
            .first()
        )
        if row:
            row.status = "completed"
            row.result_preview = (result_preview or "")[:2000]
            row.error_message = None
            row.update_time = datetime.now()
            db.commit()

    @staticmethod
    def mark_failed(db: Session, checkpoint_thread_id: str, message: str) -> None:
        row = (
            db.query(AgentTaskRun)
            .filter(AgentTaskRun.checkpoint_thread_id == checkpoint_thread_id)
            .first()
        )
        if row:
            row.status = "failed"
            row.error_message = (message or "")[:4000]
            row.update_time = datetime.now()
            db.commit()

    @staticmethod
    def list_runs(
        db: Session, limit: int = 50, session_id: str | None = None
    ) -> list[dict]:
        q = db.query(AgentTaskRun).order_by(desc(AgentTaskRun.update_time))
        if session_id:
            q = q.filter(AgentTaskRun.session_id == session_id)
        rows = q.limit(limit).all()
        return [
            {
                "checkpoint_thread_id": r.checkpoint_thread_id,
                "session_id": r.session_id,
                "status": r.status,
                "task_preview": r.task_preview,
                "result_preview": r.result_preview,
                "error_message": r.error_message,
                "create_time": r.create_time.isoformat() if r.create_time else None,
                "update_time": r.update_time.isoformat() if r.update_time else None,
            }
            for r in rows
        ]


task_run_repo = TaskRunRepository()
