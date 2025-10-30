"""MCP (Model Context Protocol) server module for Japanese transit search.

This module provides MCP server implementation that exposes transit search
and station management functionality through the Model Context Protocol.
"""

from .server import TransitMCPServer, main

__all__ = ["TransitMCPServer", "main"]
