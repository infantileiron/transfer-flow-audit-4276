"""测试引导：在导入后端任何模块前固定一个临时 SQLite 库，供多个测试模块共享。"""
import os,tempfile
_DB_FD,_DB_PATH=tempfile.mkstemp(suffix=".sqlite")
os.environ.setdefault("DATABASE_URL","sqlite:///"+_DB_PATH)
os.environ.setdefault("REDIS_URL","redis://127.0.0.1:6399/0")
os.environ.setdefault("JWT_SECRET","test-secret")
os.environ.setdefault("SEED_DEMO","false")
from src.config.database import Base,engine,Session
import src.models  # noqa: F401  注册全部表到 metadata
Base.metadata.create_all(engine)
