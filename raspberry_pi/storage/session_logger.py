from datetime import datetime, timezone

from .sqlite_db import SQLiteDB


class SessionLogger:
    def __init__(self, db_path: str = 'raspberry_pi/storage/local_measurements.db'):
        self.db = SQLiteDB(path=db_path)

    def log(self, point: str, measurement: dict):
        now = datetime.now(timezone.utc).isoformat()
        self.db.insert_session(point=point, payload=measurement, created_at=now)
        return {'saved': True, 'at': now}
