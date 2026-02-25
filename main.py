import os
import json
import datetime
import numpy as np
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider, JWTVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.context import Context

from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import chromadb

# Machine Learning for Semantic Search
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

from database import SessionLocal, Note

load_dotenv()

# Initialize our ML embedding model locally (downloads once)
encoder = SentenceTransformer("all-MiniLM-L6-v2")

# Initialize ChromaDB vector store
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="notes_collection")

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

def _get_user_id():
    token = get_access_token()
    return token.client_id if token else "anonymous"

# ================= TOOLS ================= #

def _scrape_url(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.extract()
                
            text = soup.get_text(separator=' ', strip=True)
            # Safely truncate the text because context lengths can blow up
            return text[:2000] + ("..." if len(text) > 2000 else "")
    except Exception as e:
        return f"[Failed to scrape URL {url}: {str(e)}]"

@mcp.tool()
def get_my_notes() -> str:
    """Get all standard notes for the user"""
    user_id = _get_user_id()
    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
        
    if not notes:
        return f"No notes found for {user_id}."
        
    formatted = []
    for n in notes:
        category = f"[{n.category}] " if n.category else ""
        formatted.append(f"ID {n.id} {category}: {n.content}")
        
    return "\n".join(formatted)

@mcp.tool()
def add_note(
    content: str, 
    account_id: str = None,
    file_path: str = None, 
    line_number: int = None, 
    code_snippet: str = None
) -> str:
    """Add a note for a user, automatically embedding it for AI semantic search.
    Provides optional context injection for IDE auto-tagging, and scrapes/summarizes URLs automatically.
    """
    user_id = _get_user_id()
    # Determine if this is a "TODO" or a "Task"
    import re
    is_task_flag = 1 if re.search(r"(?i)\b(todo|fixme|meeting|task|action item)\b", content) else 0

    # 0. Auto-Enrichment (Web Scraping Support)
    web_context = None
    import re
    # Match basic URLs in the text
    url_match = re.search(r"https?://[^\s]+", content)
    if url_match:
        url = url_match.group(0)
        web_context = _scrape_url(url)
        content += f"\n\n[Enriched URL Context for {url}]:\n{web_context}"

    # 1. Generate Semantic Embeddings
    text_to_embed = content
    if code_snippet:
        text_to_embed += f"\nCode Context: {code_snippet}"
    if web_context:
        text_to_embed += f"\nWeb Context: {web_context}"
    
    embedding_vector = encoder.encode(text_to_embed).tolist()
    embedding_json = json.dumps(embedding_vector)

    with SessionLocal() as db:
        new_note = Note(
            user_id=user_id, 
            content=content,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
            web_context=web_context,
            is_task=is_task_flag,
            embedding=embedding_json
        )
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        
        # Add to ChromaDB
        collection.add(
            embeddings=[embedding_vector],
            documents=[text_to_embed],
            metadatas=[{"user_id": user_id, "note_id": new_note.id}],
            ids=[str(new_note.id)]
        )
        
    return f"Successfully saved context as Note #{new_note.id} for semantic retrieval!"

@mcp.tool()
def delete_note(note_id: int) -> str:
    """Delete a specific note using its database ID"""
    user_id = _get_user_id()
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            db.delete(note)
            db.commit()
            
            # Remove from ChromaDB
            try:
                collection.delete(ids=[str(note_id)])
            except Exception:
                pass
                
            return f"Successfully deleted note ID {note_id}."
    return "Invalid note ID or note does not belong to you."

@mcp.tool()
def search_notes(query: str, top_k: int = 5) -> str:
    """Semantic hit search through notes using ChromaDB Vector Store (RAG)"""
    user_id = _get_user_id()
    query_embedding = encoder.encode(query).tolist()
    
    # Query directly at ChromaDB natively instead of SQLite
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"user_id": user_id}
    )
    
    if not results or not results['ids'] or len(results['ids'][0]) == 0:
        return "No notes found for query."

    formatted = []
    # Chroma returns lists of lists for batching
    for i in range(len(results['ids'][0])):
        n_id = results['ids'][0][i]
        n_dist = results['distances'][0][i]
        n_doc = results['documents'][0][i]
        
        # Distance (lower is closer/better)
        text = f"[Distance: {n_dist:.2f}] Note #{n_id}:\n{n_doc}"
        formatted.append(text)

    return "\n\n".join(formatted)

@mcp.tool()
def update_note(note_id: int, new_content: str) -> str:
    """Update an existing note by its database ID. Embeddings are re-calculated automatically."""
    user_id = _get_user_id()

    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if note:
            note.content = new_content
            # Re-embed updated text
            text_to_embed = new_content
            if note.code_snippet:
                text_to_embed += f"\nCode Context: {note.code_snippet}"
            embedding_vector = encoder.encode(text_to_embed).tolist()
            note.embedding = json.dumps(embedding_vector)
            db.commit()
            
            # Update ChromaDB
            try:
                collection.update(
                    ids=[str(note_id)],
                    embeddings=[embedding_vector],
                    documents=[text_to_embed],
                    metadatas=[{"user_id": user_id, "note_id": note_id}]
                )
            except Exception:
                pass
                
            return f"Successfully updated note ID {note_id} to: {new_content}"
            
    return "Invalid note ID or note does not belong to you."

@mcp.tool()
def generate_standup_report() -> str:
    """Generate a daily standup report from notes created in the last 24 hours."""
    user_id = _get_user_id()
    yesterday_threshold = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    
    with SessionLocal() as db:
        recent_notes = db.query(Note).filter(Note.user_id == user_id, Note.created_at >= yesterday_threshold).all()
        
    if not recent_notes:
        return "You have not tracked any notes or code learnings in the last 24 hours."

    report = "### Daily Standup Report\nHere is a summary of the things tracked yesterday:\n\n"
    for n in recent_notes:
        report += f"- {n.content}\n"
        if n.file_path:
            report += f"  *(Worked in `{n.file_path}`)*\n"
            
    return report

@mcp.tool()
def ingest_project_directory(path: str) -> str:
    """Recursively reads all allowed files in a local directory, chunks them, and adds to your vector memory.
    Wait a few seconds for large directories!"""
    user_id = _get_user_id()
    if not os.path.exists(path) or not os.path.isdir(path):
        return f"Error: '{path}' is not a valid directory on your machine."

    allowed_exts = {".py", ".js", ".md", ".txt", ".json", ".ts", ".jsx", ".tsx"}
    added_chunks = 0
    with SessionLocal() as db:
        for root, _, files in os.walk(path):
            # Skip common hidden/junk folders to not pollute memory
            if any(part.startswith('.') for part in root.split(os.sep)) or "node_modules" in root:
                continue

            for file in files:
                if any(file.endswith(ext) for ext in allowed_exts):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            text = f.read()
                        
                        # Simplistic Fixed-Size Content Chunker
                        chunk_size = 2000
                        for i in range(0, len(text), chunk_size):
                            chunk_text = text[i:i+chunk_size]
                            chunk_embed_text = f"[Local File Context from {full_path}]\n\n" + chunk_text
                            emb_vec = encoder.encode(chunk_embed_text).tolist()

                            new_note = Note(
                                user_id=user_id,
                                content=chunk_text,
                                file_path=full_path,
                                embedding=json.dumps(emb_vec)
                            )
                            db.add(new_note)
                            db.commit()
                            db.refresh(new_note)
                            
                            collection.add(
                                embeddings=[emb_vec],
                                documents=[chunk_embed_text],
                                metadatas=[{"user_id": user_id, "note_id": new_note.id}],
                                ids=[str(new_note.id)]
                            )
                            added_chunks += 1
                    except Exception:
                        pass # Ignore permission denied or binary errors
                        
    return f"Successfully ingested {added_chunks} chunks from '{path}' into Vector Memory."

@mcp.tool()
def extract_todos() -> str:
    """Retrieve all your pending Action Items, TODOs, or Meetings across tracked context!"""
    user_id = _get_user_id()
    with SessionLocal() as db:
        tasks = db.query(Note).filter(Note.user_id == user_id, Note.is_task == 1).all()
        
    if not tasks:
        return "You have no pending TODOs or tasks found in memory."
        
    report = "### Extracted Action Items:\n\n"
    for t in tasks:
        report += f"- [Note ID {t.id}]: {t.content}\n"
    return report

@mcp.tool()
def organize_my_notes() -> str:
    """Automatically group your notes using Unsupervised Machine Learning (K-Means Clustering)."""
    user_id = _get_user_id()
    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
        
    embeddings = [json.loads(n.embedding) for n in notes if n.embedding]
    if len(embeddings) < 3:
        return "Not enough notes to cluster. Try adding at least 3 notes to your DB!"
        
    matrix = np.array(embeddings)
    k = min(4, len(embeddings))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    kmeans.fit(matrix)
    
    valid_notes = [n for n in notes if n.embedding]
    
    # 🧠 Dynamic Naming Logic extracting top words
    from collections import Counter
    import re
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "about", "as", "is", "are", "was", "were", "be", "been", "this", "that", "it", "of", "from", "i", "my", "me", "you", "your", "they", "them", "he", "she", "we", "not", "no", "if", "so", "how", "what", "where", "why", "can", "will", "just", "have", "has", "do", "did"}
    
    cluster_names = {}
    for i in range(k):
        cluster_indices = np.where(kmeans.labels_ == i)[0]
        words = []
        for idx in cluster_indices:
            text = valid_notes[idx].content.lower()
            tokens = re.findall(r'\b[a-z]{3,}\b', text)
            words.extend([w for w in tokens if w not in stop_words])
            
        if words:
            most_common = Counter(words).most_common(2)
            cluster_names[i] = " ".join([w[0].capitalize() for w in most_common])
        else:
            cluster_names[i] = f"Topic {i}"
    
    with SessionLocal() as db:
        for idx, cluster_label in enumerate(kmeans.labels_):
            cluster_name = cluster_names[cluster_label]
            n_in_db = db.query(Note).filter(Note.id == valid_notes[idx].id).first()
            if n_in_db:
                n_in_db.category = cluster_name
        db.commit()
    
    return f"Successfully grouped {len(embeddings)} notes mathematically into {k} different theme clusters. Try 'get_my_notes' to see the categories attached!"

# ================= RESOURCES ================= #

@mcp.resource("note://{note_id}")
def read_note_resource(note_id: int) -> str:
    """Read a specific note as a raw structured resource directly into AI context."""
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return "Note not found."
        
        content = f"# Note ID: {note.id}\n**Created:** {note.created_at} UTC\n\n{note.content}"
        if note.file_path:
            content += f"\n\n**File Reference:** `{note.file_path}`"
            if note.line_number:
                content += f" (Line {note.line_number})"
        if note.code_snippet:
            content += f"\n\n```python\n{note.code_snippet}\n```"
            
        return content

# ================= PROMPTS ================= #

@mcp.prompt("project_onboarding")
def project_onboarding() -> str:
    """A powerful onboarding prompt template combining all the past lessons tracked dynamically in the database."""
    user_id = "anonymous" 
    with SessionLocal() as db:
        notes = db.query(Note).filter(Note.user_id == user_id).all()
    
    if not notes:
        return "Hello Assistant! You are an expert developer helping with a new project. There is no historical wisdom tracked yet. Assist the user flawlessly!"
    
    prompt = "Hello Assistant! You are an expert developer helping to onboard or answer questions on this project.\n"
    prompt += "\nThe developer has specifically tracked the following architectural rules, past mistakes, and project wisdom to guide your advice:\n\n---\n"
    
    for idx, n in enumerate(notes, 1):
        prompt += f"{idx}. {n.content}"
        if n.code_snippet:
            prompt += f" (Review code block snippet reference if needed from `note://{n.id}`)"
        prompt += "\n"
    
    prompt += "\n---\nPlease strictly use this wisdom when suggesting code fixes, design patterns, or refactoring in this workspace. Follow all rules outlined above."
    return prompt

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