import json
import sqlite3
from pathlib import Path


class SQLiteDB:
    def __init__(self, path: str = 'raspberry_pi_data.db'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, point TEXT, payload TEXT, created_at TEXT)'
        )
        self.conn.commit()

    def insert_session(self, point: str, payload: dict, created_at: str):
        self.conn.execute(
            'INSERT INTO sessions (point, payload, created_at) VALUES (?, ?, ?)',
            (point, json.dumps(payload, ensure_ascii=False), created_at),
        )
        self.conn.commit()
