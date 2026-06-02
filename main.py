import os
import re
import time
import datetime
import numpy as np
from collections import Counter, defaultdict
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider, JWTVerifier
from fastmcp.server.dependencies import get_access_token

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import httpx
from bs4 import BeautifulSoup

from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

from database import SessionLocal, Note, init_db

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
BASE_URL = os.getenv("BASE_URL", "http://0.0.0.0:8000")
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

# ── ML model (loaded once at startup) ────────────────────────────────────────

encoder = SentenceTransformer("all-MiniLM-L6-v2")

# ── Database bootstrap ────────────────────────────────────────────────────────

init_db()

# ── Auth setup ────────────────────────────────────────────────────────────────

if AUTH_ENABLED:
    jwt_verifier = JWTVerifier(
        jwks_uri=f"{os.environ['STYTCH_DOMAIN']}/.well-known/jwks.json",
        issuer=os.environ["STYTCH_DOMAIN"],
        algorithm="RS256",
        audience=os.environ["STYTCH_PROJECT_ID"],
    )
    auth = RemoteAuthProvider(
        token_verifier=jwt_verifier,
        authorization_servers=[os.environ["STYTCH_DOMAIN"]],
        base_url=BASE_URL,
    )
    mcp = FastMCP(name="Notes App", auth=auth)
else:
    mcp = FastMCP(name="Notes App")

# ── Rate limiting middleware ───────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter — 60 requests per IP per minute."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._log: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window_seconds
        self._log[ip] = [t for t in self._log[ip] if t > cutoff]
        if len(self._log[ip]) >= self.max_requests:
            return JSONResponse(
                {"error": "Rate limit exceeded. Try again later."}, status_code=429
            )
        self._log[ip].append(now)
        return await call_next(request)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_id() -> str:
    token = get_access_token()
    if token is None:
        if not AUTH_ENABLED:
            return "dev_user"
        raise PermissionError("Authentication required")
    # JWT 'sub' claim is the Stytch user/member ID
    return token.subject or token.client_id


def _scrape_url(url: str) -> str:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style"]):
                tag.extract()
            text = soup.get_text(separator=" ", strip=True)
            return text[:2000] + ("..." if len(text) > 2000 else "")
    except Exception as exc:
        return f"[Failed to scrape {url}: {exc}]"

# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_my_notes() -> str:
    """Get all notes for the current user."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
    if not notes:
        return "No notes found."
    lines = []
    for n in notes:
        prefix = f"[{n.category}] " if n.category else ""
        lines.append(f"ID {n.id} {prefix}: {n.content}")
    return "\n".join(lines)


@mcp.tool()
def add_note(
    content: str,
    file_path: str = None,
    line_number: int = None,
    code_snippet: str = None,
) -> str:
    """Add a note. Embeds it for semantic search automatically.
    Any URL in the content is scraped and its text is stored as extra context."""
    user_id = _get_user_id()
    is_task = 1 if re.search(r"(?i)\b(todo|fixme|meeting|task|action item)\b", content) else 0

    web_context = None
    url_match = re.search(r"https?://[^\s]+", content)
    if url_match:
        url = url_match.group(0)
        web_context = _scrape_url(url)
        content += f"\n\n[Enriched URL Context for {url}]:\n{web_context}"

    text_to_embed = content
    if code_snippet:
        text_to_embed += f"\nCode Context: {code_snippet}"
    if web_context:
        text_to_embed += f"\nWeb Context: {web_context}"

    embedding = encoder.encode(text_to_embed).tolist()

    with SessionLocal() as db:
        note = Note(
            user_id=user_id,
            content=content,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
            web_context=web_context,
            is_task=is_task,
            embedding=embedding,
        )
        db.add(note)
        db.commit()
        db.refresh(note)

    return f"Note #{note.id} saved."


@mcp.tool()
def delete_note(note_id: int) -> str:
    """Delete a note by its ID."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            db.delete(note)
            db.commit()
            return f"Deleted note #{note_id}."
    return "Note not found or does not belong to you."


@mcp.tool()
def search_notes(query: str, top_k: int = 5) -> str:
    """Semantic search through notes using vector cosine distance."""
    user_id = _get_user_id()
    query_embedding = encoder.encode(query).tolist()

    with SessionLocal() as db:
        results = (
            db.query(Note)
            .filter(Note.user_id == user_id, Note.embedding.isnot(None))
            .order_by(Note.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )

    if not results:
        return "No notes found for that query."

    return "\n\n".join(f"Note #{n.id}:\n{n.content}" for n in results)


@mcp.tool()
def update_note(note_id: int, new_content: str) -> str:
    """Update a note's content and re-embed it."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            note.content = new_content
            text_to_embed = new_content
            if note.code_snippet:
                text_to_embed += f"\nCode Context: {note.code_snippet}"
            note.embedding = encoder.encode(text_to_embed).tolist()
            db.commit()
            return f"Updated note #{note_id}."
    return "Note not found or does not belong to you."


@mcp.tool()
def generate_standup_report() -> str:
    """Generate a standup report from notes created in the last 24 hours."""
    user_id = _get_user_id()
    threshold = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    with SessionLocal() as db:
        recent = db.query(Note).filter(
            Note.user_id == user_id, Note.created_at >= threshold
        ).all()
    if not recent:
        return "No notes tracked in the last 24 hours."
    lines = ["### Daily Standup Report\n"]
    for n in recent:
        lines.append(f"- {n.content}")
        if n.file_path:
            lines.append(f"  *(in `{n.file_path}`)*")
    return "\n".join(lines)


@mcp.tool()
def extract_todos() -> str:
    """Retrieve all pending TODOs, tasks, and action items."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        tasks = db.query(Note).filter(Note.user_id == user_id, Note.is_task == 1).all()
    if not tasks:
        return "No pending TODOs found."
    lines = ["### Action Items\n"]
    for t in tasks:
        lines.append(f"- [#{t.id}]: {t.content}")
    return "\n".join(lines)


@mcp.tool()
def organize_my_notes() -> str:
    """Group your notes into topic clusters using K-Means (up to 1000 notes)."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        notes = (
            db.query(Note)
            .filter(Note.user_id == user_id, Note.embedding.isnot(None))
            .limit(1000)
            .all()
        )

    if len(notes) < 3:
        return "Add at least 3 notes before organizing."

    matrix = np.array([n.embedding for n in notes])
    k = min(4, len(notes))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    kmeans.fit(matrix)

    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "with", "by", "about", "as", "is", "are", "was", "were", "be", "been",
        "this", "that", "it", "of", "from", "i", "my", "me", "you", "your",
        "they", "them", "he", "she", "we", "not", "no", "if", "so", "how",
        "what", "where", "why", "can", "will", "just", "have", "has", "do", "did",
    }
    cluster_names: dict[int, str] = {}
    for i in range(k):
        indices = np.where(kmeans.labels_ == i)[0]
        words: list[str] = []
        for idx in indices:
            tokens = re.findall(r"\b[a-z]{3,}\b", notes[idx].content.lower())
            words.extend(w for w in tokens if w not in stop_words)
        if words:
            top = Counter(words).most_common(2)
            cluster_names[i] = " ".join(w.capitalize() for w, _ in top)
        else:
            cluster_names[i] = f"Topic {i}"

    with SessionLocal() as db:
        for idx, label in enumerate(kmeans.labels_):
            n = db.query(Note).filter(Note.id == notes[idx].id).first()
            if n:
                n.category = cluster_names[int(label)]
        db.commit()

    return f"Organized {len(notes)} notes into {k} clusters. Run get_my_notes to see categories."

# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("note://{note_id}")
def read_note_resource(note_id: int) -> str:
    """Read a specific note as a structured resource into AI context."""
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return "Note not found."
        body = f"# Note #{note.id}\n**Created:** {note.created_at} UTC\n\n{note.content}"
        if note.file_path:
            body += f"\n\n**File:** `{note.file_path}`"
            if note.line_number:
                body += f" (Line {note.line_number})"
        if note.code_snippet:
            body += f"\n\n```\n{note.code_snippet}\n```"
        return body

# ── Prompts ───────────────────────────────────────────────────────────────────

@mcp.prompt("project_onboarding")
def project_onboarding() -> str:
    """Build a system prompt from stored notes for AI-assisted project onboarding."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
    if not notes:
        return (
            "You are an expert developer. No historical wisdom has been tracked yet. "
            "Assist the user directly."
        )
    lines = [
        "You are an expert developer. The developer has tracked the following rules and wisdom:\n\n---"
    ]
    for idx, n in enumerate(notes, 1):
        entry = f"{idx}. {n.content}"
        if n.code_snippet:
            entry += f" (see `note://{n.id}` for code context)"
        lines.append(entry)
    lines.append("\n---\nUse this wisdom when suggesting code fixes, patterns, or refactors.")
    return "\n".join(lines)

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level="info",
        middleware=[
            Middleware(RateLimitMiddleware, max_requests=60, window_seconds=60),
            Middleware(
                CORSMiddleware,
                allow_origins=ALLOWED_ORIGINS,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        ],
    )
