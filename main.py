from fastmcp import FastMCP
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.cors import Middleware

load_dotenv()

mcp=FastMCP(name="Notes App")

#MCP TOOLS
@mcp.tool()
def get_my_notes()->str:
    """Get all notes for a user"""
    return "no notes"

@mcp.tool()
def add_note(content: str)->str:
    """add a note for a user"""
    return f"added note: {content}"

#running the MCP SERVER
if __name__ == "__main__":
    mcp.run(
        transport="http", #transport type
        host="127.0.0.1", #specifying the host (if you have a domain you can replace)
        port=8000,
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