# Notes App MCP Server

An advanced [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built from scratch using the [FastMCP](https://github.com/jlowin/fastmcp) Python framework.

This application acts as a bridge between your preferred AI Assistant (Codex, Claude, Cursor) and a local SQLite database, giving the AI the ability to manage and query a persistent personal notebook.

## Features Currently Implemented

*   **Persistent SQLite Storage:** Notes are safely persisted using SQLAlchemy (`database.py`) and stored in a local `notes.db` file.
*   **Full CRUD Capabilities:** The server exposes the following tools directly to the AI:
    *   `add_note`: Write and save a new note.
    *   `get_my_notes`: Read all saved notes.
    *   `update_note`: Modify an existing note using its ID.
    *   `delete_note`: Permanently remove a note using its ID.
    *   `search_notes`: Search notes by keyword.
*   **Authentication Foundations (WIP):** Includes prepared code for remote JWT Authentication and OAuth Protected Resource Routing via Stytch integration. (*Currently disabled for ease of local testing.*)

## Prerequisites

1.  Python 3.12+
2.  [`uv`](https://docs.astral.sh/uv/) package manager installed.

## Setup & Running Locally

1. **Clone the repository and enter the directory.**

2. **Set up `.env` File**
   Create a `.env` file in the root directory (used for future authentication steps):
   ```env
   STYTCH_DOMAIN=your_stytch_domain_here
   STYTCH_PROJECT_ID=your_stytch_project_id_here
   ```

3. **Start the MCP Server**
   ```bash
   uv run main.py
   ```
   *This automatically provisions the SQLite database (`notes.db`), installs dependencies, and runs the server on `http://127.0.0.1:8000` over SSE/HTTP.*

## Connecting to an AI Assistant (Codex)

With the server running securely on your local network, you can instantly give Codex access to it.

1.  Open a new terminal tab and connect Codex to the local `/mcp` endpoint:
    ```bash
    codex mcp add notes-app --url http://127.0.0.1:8000/mcp
    ```
2.  Start the Codex console:
    ```bash
    codex
    ```
3.  **Try it out!** Just tell the AI:
    > *"Save a note that my favorite color is blue."*
    > *"Tell me everything in my notes."*

## Upcoming Features Roadmap
- [ ] Connect the `RemoteAuthProvider` directly with a frontend logic for real user differentiation via Stytch JWTs.
- [ ] Add `created_at` and tags for rich note structures.
- [ ] Package the MCP tool so anyone can run it instantly using `uvx`.
- [ ] Deploy seamlessly to a cloud provider with a managed PostgreSQL connection.
