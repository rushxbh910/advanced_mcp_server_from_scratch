"""
End-to-end test suite for the Notes MCP server.
Runs against a live server started in a subprocess.
AUTH_ENABLED must be false (dev mode) for these tests.
"""
import asyncio
import os
import subprocess
import sys
import time
import httpx

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8000/mcp"
DB_URL = "postgresql://notesuser:testpass123@localhost:5433/notesdb"

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"


def header(text: str):
    print(f"\n{'─'*55}")
    print(f"  {text}")
    print(f"{'─'*55}")


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}")
    if detail:
        print(f"         {detail}")
    if not condition:
        raise SystemExit(1)


async def wait_for_server(timeout: int = 60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            async with httpx.AsyncClient() as http:
                r = await http.get(SERVER_URL, timeout=2)
                if r.status_code < 500:
                    return
        except Exception:
            pass
        await asyncio.sleep(1)
    raise SystemExit("Server did not start in time")


async def run_tests():
    header("Connecting to MCP server")
    await wait_for_server()
    print(f"  Server reachable at {SERVER_URL}")

    async with Client(SERVER_URL) as client:
        header("1  Tool discovery")
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "add_note", "get_my_notes", "delete_note", "search_notes",
            "update_note", "generate_standup_report", "extract_todos", "organize_my_notes",
        }
        check("All tools registered", expected <= tool_names, str(tool_names))

        header("2  add_note — plain note")
        r = await client.call_tool("add_note", {"content": "Learn FastMCP and deploy it properly"})
        note_id_1 = None
        text = r.content[0].text if r and r.content else ""
        check("Returns success message", "Note #" in text, text)
        note_id_1 = int(text.split("#")[1].split()[0])

        header("3  add_note — TODO detection")
        r = await client.call_tool("add_note", {"content": "TODO: write integration tests for the MCP server"})
        text = r.content[0].text if r and r.content else ""
        check("Returns success message", "Note #" in text, text)
        note_id_todo = int(text.split("#")[1].split()[0])

        header("4  add_note — with code snippet")
        r = await client.call_tool("add_note", {
            "content": "Semantic search using pgvector cosine distance",
            "code_snippet": "Note.embedding.cosine_distance(query_embedding)",
            "file_path": "main.py",
        })
        text = r.content[0].text if r and r.content else ""
        check("Returns success message", "Note #" in text, text)
        note_id_code = int(text.split("#")[1].split()[0])

        header("5  add_note — machine learning note (for clustering)")
        r = await client.call_tool("add_note", {"content": "K-Means clustering organises embeddings into topic groups"})
        text = r.content[0].text if r and r.content else ""
        check("Returns success message", "Note #" in text, text)

        header("6  get_my_notes")
        r = await client.call_tool("get_my_notes", {})
        text = r.content[0].text if r and r.content else ""
        check("Returns at least 3 notes", text.count("ID ") >= 3, text[:200])

        header("7  search_notes — semantic similarity")
        r = await client.call_tool("search_notes", {"query": "vector database similarity search", "top_k": 3})
        text = r.content[0].text if r and r.content else ""
        check("Returns results", "Note #" in text, text[:300])
        check("pgvector note appears in top-3", "pgvector" in text.lower() or "semantic" in text.lower(), text[:300])

        header("8  update_note")
        r = await client.call_tool("update_note", {
            "note_id": note_id_1,
            "new_content": "Learn FastMCP, pgvector, and deploy to Railway",
        })
        text = r.content[0].text if r and r.content else ""
        check("Returns updated confirmation", f"#{note_id_1}" in text, text)

        header("9  extract_todos")
        r = await client.call_tool("extract_todos", {})
        text = r.content[0].text if r and r.content else ""
        check("TODO note appears", str(note_id_todo) in text, text[:200])

        header("10  generate_standup_report")
        r = await client.call_tool("generate_standup_report", {})
        text = r.content[0].text if r and r.content else ""
        check("Report contains notes from today", "Standup" in text or "tracked" in text.lower(), text[:200])

        header("11  organize_my_notes — K-Means clustering")
        r = await client.call_tool("organize_my_notes", {})
        text = r.content[0].text if r and r.content else ""
        check("Clustering ran successfully", "cluster" in text.lower() or "organized" in text.lower(), text)

        header("12  get_my_notes — categories applied")
        r = await client.call_tool("get_my_notes", {})
        text = r.content[0].text if r and r.content else ""
        check("At least one category tag present", "[" in text, text[:300])

        header("13  delete_note")
        r = await client.call_tool("delete_note", {"note_id": note_id_code})
        text = r.content[0].text if r and r.content else ""
        check("Deletion confirmed", "Deleted" in text, text)

        r = await client.call_tool("delete_note", {"note_id": note_id_code})
        text = r.content[0].text if r and r.content else ""
        check("Deleting non-existent note returns error msg", "not found" in text.lower(), text)

        header("14  Resources — note://{id}")
        resources = await client.list_resources()
        # Resources are dynamic (URI templates); just verify the template is registered
        templates = await client.list_resource_templates()
        names = [str(t.uriTemplate) for t in templates]
        check("note:// template registered", any("note" in n for n in names), str(names))

        header("15  Prompts")
        prompts = await client.list_prompts()
        pnames = [p.name for p in prompts]
        check("project_onboarding prompt registered", "project_onboarding" in pnames, str(pnames))

        header("ALL TESTS PASSED")
        print()


def start_server() -> subprocess.Popen:
    env = {
        **os.environ,
        "DATABASE_URL": DB_URL,
        "AUTH_ENABLED": "false",
        "PORT": "8000",
        # suppress uv venv warning noise
        "VIRTUAL_ENV": "",
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


if __name__ == "__main__":
    server = start_server()
    try:
        asyncio.run(run_tests())
    finally:
        server.terminate()
        server.wait()
