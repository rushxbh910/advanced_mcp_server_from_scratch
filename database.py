import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///notes.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    # Code context auto-tagging
    file_path = Column(String, nullable=True)
    line_number = Column(Integer, nullable=True)
    code_snippet = Column(Text, nullable=True)
    
    # Auto-enrichment (web scraping context)
    web_context = Column(Text, nullable=True)
    
    # Automatic categorization
    category = Column(String, nullable=True)
    
    # Task/todo extraction tracker
    is_task = Column(Integer, default=0) # SQLite uses 0/1 for bools
    
    # Semantic search embeddings (stored as JSON string list of floats)
    embedding = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)
