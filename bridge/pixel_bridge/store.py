import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Callable

from .config import Settings
from .models import Action, CreateAction, DeviceResult


class StoreError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code, self.detail = status_code, detail


class Store:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time):
        self.settings, self.clock = settings, clock
        settings.database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        settings.database.touch(mode=0o600, exist_ok=True)
        settings.database.chmod(0o600)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                request_json TEXT NOT NULL, action TEXT NOT NULL, params_json TEXT NOT NULL,
                status TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                detail TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS action_queue ON actions(status, created_at)")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.settings.database, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                now = self.clock()
                # A delivered action might already have caused an intent when its
                # result was lost. Never claim it again or call it expired safely.
                db.execute("UPDATE actions SET status='expired', detail='Not delivered before deadline' WHERE status='queued' AND expires_at<=?", (now,))
                db.execute("UPDATE actions SET status='unknown', detail='Confirmation or result deadline elapsed; do not replay' WHERE status='awaiting_confirmation' AND expires_at<=?", (now,))
                yield db, now
                db.commit()
            except StoreError:
                # Business rejections happen before mutation of the requested
                # action. Keep deadline transitions terminal even if a late
                # result conflicts, including across a later clock correction.
                db.commit()
                raise
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def action(row) -> Action:
        return Action(id=row["id"], action=row["action"], params=json.loads(row["params_json"]),
                      status=row["status"], created_at=row["created_at"], expires_at=row["expires_at"], detail=row["detail"])

    def create(self, request: CreateAction) -> Action:
        value = request.model_dump()
        key = value.pop("idempotency_key")
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self.transaction() as (db, now):
            previous = db.execute("SELECT * FROM actions WHERE idempotency_key=?", (key,)).fetchone()
            if previous:
                if previous["request_json"] != canonical:
                    raise StoreError(409, "Idempotency key already identifies a different request")
                return self.action(previous)
            if db.execute("SELECT count(*) FROM actions").fetchone()[0] >= self.settings.max_records:
                raise StoreError(507, "Session record capacity reached; archive state and rotate both credentials before a new session")
            if db.execute("SELECT count(*) FROM actions WHERE status IN ('queued','awaiting_confirmation')").fetchone()[0] >= self.settings.max_pending:
                raise StoreError(429, "Pending action capacity reached")
            action_id = str(uuid.uuid4())
            db.execute("INSERT INTO actions VALUES (?,?,?,?,?,'queued',?,?,NULL)",
                       (action_id, key, canonical, value["action"], json.dumps(value["params"]), now, now + self.settings.ttl_seconds))
            return self.action(db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())

    def get(self, action_id: str) -> Action:
        with self.transaction() as (db, _):
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise StoreError(404, "Action not found")
            return self.action(row)

    def claim(self) -> Action | None:
        with self.transaction() as (db, _):
            row = db.execute("SELECT * FROM actions WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE actions SET status='awaiting_confirmation' WHERE id=?", (row["id"],))
            return self.action(db.execute("SELECT * FROM actions WHERE id=?", (row["id"],)).fetchone())

    def report(self, action_id: str, result: DeviceResult) -> Action:
        with self.transaction() as (db, _):
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                raise StoreError(404, "Action not found")
            if row["status"] != "awaiting_confirmation":
                if row["status"] == result.status and row["detail"] == result.detail:
                    return self.action(row)
                raise StoreError(409, "Action is not awaiting a result; do not replay")
            db.execute("UPDATE actions SET status=?, detail=? WHERE id=?", (result.status, result.detail, action_id))
            return self.action(db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone())
