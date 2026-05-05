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
    def save_error_log(db: Session, err: Exception):
        record = ErrorLog(
            error_msg=str(err),
            traceback=traceback.format_exc()
        )
        db.add(record)
        db.commit()

log_repo = LogRepository()