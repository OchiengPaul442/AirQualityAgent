"""
MCP Client Helper

This module provides utilities for the agent to connect to other MCP servers.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """
    A client to interact with other MCP servers via stdio.
    """

    def __init__(
        self, server_command: str, server_args: list[str], env: dict[str, str] | None = None
    ):
        self.server_params = StdioServerParameters(
            command=server_command, args=server_args, env=env
        )
        self.session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator["MCPClient"]:
        """
        Connect to the MCP server.
        """
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            self._exit_stack = stack
            try:
                transport = await stack.enter_async_context(stdio_client(self.server_params))
                self.session = await stack.enter_async_context(
                    ClientSession(transport[0], transport[1])
                )
                assert self.session is not None
                await self.session.initialize()
                logger.info("Connected to MCP server")
                yield self
            except Exception as e:
                logger.error(f"Failed to connect to MCP server: {e}")
                raise

    async def list_tools(self) -> list[Any]:
        """List available tools on the server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        return await self.session.call_tool(name, arguments)
