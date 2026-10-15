"""The MCP server (prd-mcp.md A.1): mounted at ``/mcp`` in the same FastAPI app,
served by the MCP Python SDK over stateless streamable HTTP. A thin adapter
beside the routes — tools validate input and call services."""
