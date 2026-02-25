from fastapi import FastAPI
from database import SessionLocal, Note
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/api/notes")
def get_notes():
    with SessionLocal() as db:
        notes = db.query(Note).all()
        return [
            {
                "id": n.id,
                "content": n.content,
                "category": n.category,
                "is_task": n.is_task,
                "file_path": n.file_path,
                "code_snippet": n.code_snippet,
                "web_context": n.web_context,
                "created_at": n.created_at.isoformat() if n.created_at else None
            }
            for n in notes
        ]
