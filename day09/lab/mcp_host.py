"""
mcp_host.py — Real MCP HTTP Server Host
Sprint 3 Bonus: Implement HTTP server with FastAPI.

Dùng uvicorn để khởi chạy:
    python -X utf8 mcp_host.py
Hoặc:
    uvicorn mcp_host:app --reload

Endpoints:
    GET  /tools       → List all available tools
    POST /call/{name} → Call a specific tool
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Import official tool logic from mcp_server.py
from mcp_server import list_tools, dispatch_tool, TOOL_SCHEMAS

app = FastAPI(
    title="Day 09 MCP HTTP Server",
    description="Real HTTP implementation of Model Context Protocol for Bonus Points.",
    version="1.0.0"
)

class ToolCallRequest(BaseModel):
    arguments: Dict[str, Any]

@app.get("/")
def read_root():
    return {
        "status": "online",
        "mcp_version": "1.0-mock-http",
        "endpoints": ["/tools", "/call/{tool_name}"]
    }

@app.get("/tools")
def get_tools():
    """MCP Discovery: Trả về danh sách tool schemas."""
    return {"tools": list_tools()}

@app.post("/call/{tool_name}")
def call_tool(tool_name: str, request: ToolCallRequest):
    """MCP Execution: Gọi tool tương ứng với input."""
    if tool_name not in TOOL_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found.")
    
    print(f"  [HTTP Server] Calling tool: {tool_name} with args: {request.arguments}")
    
    result = dispatch_tool(tool_name, request.arguments)
    
    if "error" in result:
        # Trong thực tế có thể trả về 400, nhưng MCP thường trả về error trong body
        return {"is_error": True, "content": result}
    
    return {"is_error": False, "content": result}

if __name__ == "__main__":
    print("🚀 Starting MCP HTTP Server on http://localhost:8000")
    print("📋 Discovery endpoint: http://localhost:8000/tools")
    uvicorn.run(app, host="0.0.0.0", port=8000)
