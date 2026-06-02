import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size


class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    file_path = Column(String, nullable=True)
    line_number = Column(Integer, nullable=True)
    code_snippet = Column(Text, nullable=True)
    web_context = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    is_task = Column(Integer, default=0)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)


def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
