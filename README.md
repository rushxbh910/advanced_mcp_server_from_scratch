# MCP Notes App: AI-Powered "Second Brain"

An advanced [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built from scratch using the [FastMCP](https://github.com/jlowin/fastmcp) Python framework.

This application acts as a powerful bridge between your preferred AI Assistant (Codex, Claude, Cursor) and your local environment, transforming it into an immortal, infinitely scaling "Second Brain" for developers.

## Magic Features Currently Implemented

*   **Dual-Database Architecture:** Notes are safely persisted as structured text using `SQLAlchemy` (SQLite), while mathematical vector representations are automatically pushed into a high-performance local **ChromaDB** vector store for semantic context processing.
*   **Semantic RAG Search:** Because 100% of your notes are vectorized using `sentence-transformers`, you can search your codebase learning by conceptual meaning rather than keyword matching natively.
*   **Auto-Enrichment (Web Scraping):** If you give the AI a URL (like a GitHub issue or a Wikipedia article), the FastMCP server will pause, fetch the webpage securely using a macOS User-Agent header, slice the raw text out of the HTML, and embed the context into your Vector memory automatically!
*   **Code Context Auto-Tagging:** When interacting via an IDE like Cursor, the `add_note` tool automatically reads your current `file_path` and `code_snippet` being highlighted, and binds that code into the vector embedding for future queries.
*   **Local Directory Ingestion:** The `ingest_project_directory` tool allows you to point the AI at any local codebase on your computer. It slices every Python, JavaScript, and Markdown file into chunks and dumps the source code directly into your vector workspace.
*   **Intelligent Todo/Task Extraction:** The server natively uses NLP regex to track if an input is an "Action Item", "TODO", or "Meeting", allowing you to generate comprehensive action reports across your entire database dynamically.
*   **Machine Learning Organizer:** The `organize_my_notes` tool executes an Unsupervised Machine Learning algorithm (`KMeans` clustering) over every vector in your Chroma database to mathematically discover thematic buckets (like "Frontend Issues" or "DevOps") and labels your notes automatically!
*   **Dynamic Onboarding Prompts & Resources:** Seamlessly inject `@mcp.prompt("project_onboarding")` into your AI context window to synthesize all of your past historical notes into rules for the AI. Access files natively via `@mcp.resource("note://{note_id}")`.

## Complete Tool Suite Exposed

The AI has access to the following full CRUD + ML operations:
1. `add_note`: Write and save a new note (with auto file-context & URL scraping).
2. `get_my_notes`: Read all saved notes with their ML Clusters.
3. `search_notes`: Perform Semantic RAG search natively on ChromaDB.
4. `update_note`: Modify an existing note and instantly re-embed it.
5. `delete_note`: Permanently sync note deletion across both SQLite and ChromaDB.
6. `ingest_project_directory`: Parse a codebase into semantic chunks.
7. `extract_todos`: Generate a markdown report of pending tasks.
8. `organize_my_notes`: Run K-Means ML to mathematically map and group your learnings.
9. `generate_standup_report`: Filter notes across the last 24 hours.

## Prerequisites

1.  Python 3.12+
2.  [`uv`](https://docs.astral.sh/uv/) package manager installed.

## Setup & Running Locally

1. **Clone the repository and enter the directory.**

2. **Start the MCP Server**
   ```bash
   uv run main.py
   ```
   *This automatically provisions the dual databases (`notes.db` and `chroma_db/`), downloads the `MiniLM-L6-v2` Local HuggingFace embedding model, and runs the fastmcp server on `http://127.0.0.1:8000` via SSE transport.*

*(Note: JWT Authentication and OAuth via Stytch is fully written into `main.py` but commented out/disabled for seamless local developer testing setup at the moment).*

## Connecting to an AI Assistant

With the server running securely on your local machine, give the AI powers:

1.  Connect via `codex mcp` or update your `cursor_mcp.json`:
    ```bash
    codex mcp add notes-app --url http://127.0.0.1:8000/mcp
    ```
2.  Open your AI CLI/IDE and try the magic:
    > *"Save a note with this link: https://fastapi.tiangolo.com"*
    > *"Wait, use the semantic search tool to pull up what I just stored about FastAPI."*
    > *"I have a bug here. Do I have any notes clustered in the 'Backend' category that mention a similar error?"*

## Upcoming Features Roadmap
- [ ] Connect the `RemoteAuthProvider` directly with a frontend logic for real user differentiation via Stytch JWTs.
- [ ] Package the MCP tool so anyone can run it instantly using `uvx`.
- [ ] Add real `GLiNER` Named Entity Recognition instead of Regex for Todo tracking.
