import os
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider, JWTVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.context import Context

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

load_dotenv()

from database import SessionLocal, Note

jwt_verifier = JWTVerifier(
    jwks_uri=f"{os.getenv('STYTCH_DOMAIN')}/.well-known/jwks.json",
    issuer=os.getenv("STYTCH_DOMAIN"),
    algorithm="RS256",
    audience=os.getenv("STYTCH_PROJECT_ID")
)

base_url = "http://127.0.0.1:8000"

auth = RemoteAuthProvider(
    token_verifier=jwt_verifier,
    authorization_servers=[os.getenv("STYTCH_DOMAIN")],
    base_url=base_url
)

mcp = FastMCP(name="Notes App") # auth temporarily disabled for local testing

@mcp.tool()
def get_my_notes(ctx: Context) -> str:
    """Get all notes for a user"""
    token = get_access_token()
    user_id = token.client_id if token else "anonymous"

    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
        
    if not notes:
        return f"No notes found for {user_id}."
    return "\n".join(f"ID {n.id}: {n.content}" for n in notes)

@mcp.tool()
def add_note(ctx: Context, content: str) -> str:
    """Add a note for a user"""
    token = get_access_token()
    user_id = token.client_id if token else "anonymous"

    with SessionLocal() as db:
        new_note = Note(user_id=user_id, content=content)
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        
    return f"Successfully added note (ID: {new_note.id}) for {user_id}: {content}"

@mcp.tool()
def delete_note(ctx: Context, note_id: int) -> str:
    """Delete a specific note using its database ID"""
    token = get_access_token()
    user_id = token.client_id if token else "anonymous"

    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            db.delete(note)
            db.commit()
            return f"Successfully deleted note ID {note_id}."
            
    return "Invalid note ID or note does not belong to you."

@mcp.tool()
def search_notes(ctx: Context, query: str) -> str:
    """Search through the user's notes for specific keywords"""
    token = get_access_token()
    user_id = token.client_id if token else "anonymous"
    
    with SessionLocal() as db:
        # Simple exact substring match
        notes = db.query(Note).filter(Note.user_id == user_id, Note.content.ilike(f"%{query}%")).all()
        
    if not notes:
        return "No matching notes found for query."
    return "\n".join(f"ID {n.id}: {n.content}" for n in notes)

@mcp.tool()
def update_note(ctx: Context, note_id: int, new_content: str) -> str:
    """Update an existing note by its database ID"""
    token = get_access_token()
    user_id = token.client_id if token else "anonymous"

    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            note.content = new_content
            db.commit()
            return f"Successfully updated note ID {note_id} to: {new_content}"
            
    return "Invalid note ID or note does not belong to you."

if __name__ == "__main__":
    mcp.run(
        transport="http", 
        host="127.0.0.1", 
        port=8000,
        log_level="debug",
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )
        ]
    )