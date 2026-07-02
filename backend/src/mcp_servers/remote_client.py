import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mcp-remote-client")

class RemoteMCPClient:
    """
    Client for calling tools on the remote Vercel MCP Server.
    Communicates via standard HTTP POST mapping to FastMCP's exposed endpoints.
    """
    
    def __init__(self, base_url: str):
        # E.g. base_url = "https://medical-resources-mcp.vercel.app/mcp"
        self.base_url = base_url.rstrip('/')
        
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a remote MCP tool using HTTP POST.
        
        Args:
            tool_name: The name of the registered MCP tool (e.g. 'search_blood_inventory')
            arguments: Dictionary of keyword arguments for the tool
        
        Returns:
            Dictionary containing the tool output or error state
        """
        url = f"{self.base_url}/tools/{tool_name}"
        args = arguments or {}
        
        logger.info(f"Invoking remote MCP tool '{tool_name}' at {url} with args: {args}")
        
        try:
            response = requests.post(url, json=args, timeout=10)
            if response.status_code == 200:
                # FastMCP http_app tool execution returns JSON output containing results
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                logger.error(f"Remote MCP tool execution failed: HTTP {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            logger.error(f"Network error invoking remote MCP tool '{tool_name}': {str(e)}")
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}"
            }
