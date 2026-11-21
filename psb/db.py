import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app, g


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path):
    if str(path).startswith(("mysql://", "mysql+pymysql://", "mariadb://")):
        from .mysql import MySQLConnection
        return MySQLConnection(path)
    db = sqlite3.connect(path, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    return db


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config.get("DATABASE_URL") or current_app.config["DATABASE"])
    return g.db


def one(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def all_rows(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def execute(sql, args=()):
    return get_db().execute(sql, args)


@contextmanager
def transaction():
    db = get_db()
    if hasattr(db, "begin_write"):
        db.begin_write()
    else:
        db.execute("BEGIN IMMEDIATE")
    g.pending_uploads = []
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        for name in g.pending_uploads:
            path = Path(current_app.config["UPLOAD_DIR"]) / name
            if path.is_file():
                path.unlink()
        raise
    finally:
        g.pop("pending_uploads", None)


def initialize(app):
    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    if app.config.get("DATABASE_URL"):
        from .mysql import initialize_mysql
        initialize_mysql(app.config["DATABASE_URL"])
        return
    db = connect(app.config["DATABASE"])
    for path in sorted((Path(__file__).parent.parent / "migrations").glob("*.sql")):
        version = int(path.stem.split("_")[0])
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        if (
            not exists
            or not db.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
            ).fetchone()
        ):
            db.executescript(path.read_text(encoding="utf-8"))
    db.close()


def settings():
    return {r["key"]: r["value"] for r in all_rows("SELECT * FROM settings")}


def audit(entity, entity_id, action, old=None, new=None, reason=None):
    actor = g.user["id"] if getattr(g, "user", None) else None
    execute(
        "INSERT INTO audit(actor_id,entity,entity_id,action,old_value,new_value,reason,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            actor,
            entity,
            entity_id,
            action,
            json.dumps(old, ensure_ascii=False, default=str),
            json.dumps(new, ensure_ascii=False, default=str),
            reason,
            now(),
        ),
    )
