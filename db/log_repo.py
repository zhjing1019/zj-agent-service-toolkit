import traceback
from sqlalchemy.orm import Session
from db.models import ApiLog, ErrorLog

class LogRepository:
    @staticmethod
    def save_api_log(db: Session, session_id: str, task: str, response: str, status: str, ip: str):
        record = ApiLog(
            session_id=session_id,
            task=task,
            response=response,
            status=status,
            ip=ip
        )
        db.add(record)
        db.commit()

    @staticmethod
    def list_api_logs(db: Session, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = (
            db.query(ApiLog)
            .order_by(ApiLog.create_time.desc())
            .offset(max(0, offset))
            .limit(min(200, max(1, limit)))
            .all()
        )
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "task": (r.task or "")[:2000],
                    "response": (r.response or "")[:2000],
                    "status": r.status,
                    "ip": r.ip,
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
            )
        return out

    @staticmethod
    def list_error_logs(db: Session, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = (
            db.query(ErrorLog)
            .order_by(ErrorLog.create_time.desc())
            .offset(max(0, offset))
            .limit(min(200, max(1, limit)))
            .all()
        )
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "error_msg": (r.error_msg or "")[:4000],
                    "traceback": (r.traceback or "")[:8000],
                    "create_time": r.create_time.isoformat() if r.create_time else None,
                }
            )
        return out

    @staticmethod
    def save_error_log(db: Session, err: Exception):
        record = ErrorLog(
            error_msg=str(err),
            traceback=traceback.format_exc()
        )
        db.add(record)
        db.commit()

log_repo = LogRepository()