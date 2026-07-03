import logging
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger("mcp-remote-client")

class RemoteMCPClient:
    """
    Client for calling tools on the remote Vercel MCP Server.
    Uses the MCP Python SDK against the server's SSE transport.
    """
    
    def __init__(self, base_url: str, timeout_seconds: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-remote-client")

    def _normalize_arguments(self, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return arguments or {}

    async def _call_tool_async(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = self._normalize_arguments(arguments)

        async with sse_client(self.base_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)

                if getattr(result, "is_error", False):
                    return {
                        "success": False,
                        "error": self._format_error_result(result),
                    }

                data = getattr(result, "structured_content", None)
                if data is None:
                    data = self._content_to_data(getattr(result, "content", []))

                return {
                    "success": True,
                    "data": data,
                }

    def _format_error_result(self, result: Any) -> str:
        content = getattr(result, "content", [])
        if not content:
            return "Remote MCP tool returned an error"

        return self._content_to_plain_text(content) or "Remote MCP tool returned an error"

    def _content_to_plain_text(self, content: Any) -> Any:
        if isinstance(content, list):
            text_blocks = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if text is not None:
                        text_blocks.append(text)
                else:
                    text = getattr(block, "text", None)
                    if text is not None:
                        text_blocks.append(text)

            if len(text_blocks) == 1:
                return text_blocks[0]
            if text_blocks:
                return "\n".join(text_blocks)

        return content

    def _parse_structured_content(self, content: Any) -> Any:
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return content

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                decoder = json.JSONDecoder()
                offset = 0
                objects = []

                while offset < len(text):
                    while offset < len(text) and text[offset].isspace():
                        offset += 1

                    if offset >= len(text):
                        break

                    try:
                        parsed, next_offset = decoder.raw_decode(text, offset)
                    except json.JSONDecodeError:
                        return content

                    objects.append(parsed)
                    offset = next_offset

                if len(objects) == 1:
                    return objects[0]
                if objects:
                    return objects

        return content

    def _content_to_data(self, content: Any) -> Any:
        if isinstance(content, list):
            parsed_blocks = []

            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                else:
                    text = getattr(block, "text", None)

                if text is None:
                    return self._content_to_plain_text(content)

                parsed_block = self._parse_structured_content(text)
                if isinstance(parsed_block, str):
                    return self._content_to_plain_text(content)

                parsed_blocks.append(parsed_block)

            if len(parsed_blocks) == 1:
                return parsed_blocks[0]

            if parsed_blocks:
                return parsed_blocks

        return self._parse_structured_content(content)
        
    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a remote MCP tool through the MCP SDK.
        
        Args:
            tool_name: The name of the registered MCP tool (e.g. 'search_blood_inventory')
            arguments: Dictionary of keyword arguments for the tool
        
        Returns:
            Dictionary containing the tool output or error state
        """
        args = self._normalize_arguments(arguments)
        logger.info("Invoking remote MCP tool '%s' at %s with args: %s", tool_name, self.base_url, args)

        future = self._executor.submit(asyncio.run, self._call_tool_async(tool_name, args))
        try:
            return future.result(timeout=self.timeout_seconds)
        except Exception as exc:
            logger.error("Network error invoking remote MCP tool '%s': %s", tool_name, str(exc))
            return {
                "success": False,
                "error": f"Connection failed: {str(exc)}",
            }

    def search_blood_inventory(self, blood_type: str, hospital_id: Optional[str] = None) -> Dict[str, Any]:
        return self.call_tool("search_blood_inventory", {"blood_type": blood_type, "hospital_id": hospital_id})

    def search_organ_registry(self, organ_type: str, hospital_id: Optional[str] = None) -> Dict[str, Any]:
        return self.call_tool("search_organ_registry", {"organ_type": organ_type, "hospital_id": hospital_id})

    def search_equipment(self, name: Optional[str] = None, hospital_id: Optional[str] = None) -> Dict[str, Any]:
        return self.call_tool("search_equipment", {"name": name, "hospital_id": hospital_id})
