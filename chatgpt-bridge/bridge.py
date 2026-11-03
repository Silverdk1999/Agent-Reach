"""Authenticated, read-only Agent Reach CLI → MCP bridge.

Requires Agent Reach 1.6+ installed on the execution host.
"""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
from urllib.parse import urlsplit

READABLE_CHANNELS = frozenset({
    "web", "youtube", "github", "v2ex", "bilibili", "reddit", "twitter",
    "xiaohongshu", "instagram", "facebook", "linkedin", "xueqiu",
    "xiaoyuzhou", "boss", "douyin",
})
READ_DOMAINS = frozenset({
    "youtube.com", "youtu.be", "github.com", "raw.githubusercontent.com",
    "reddit.com", "redd.it", "x.com", "twitter.com", "bilibili.com",
    "b23.tv", "xiaohongshu.com", "xhslink.com", "instagram.com",
    "facebook.com", "fb.com", "linkedin.com", "v2ex.com", "xueqiu.com",
    "xiaoyuzhoufm.com", "zhipin.com", "douyin.com", "iesdouyin.com",
})
MAX_OUTPUT_BYTES = 250_000
MAX_QUERY_CHARS = 350
COMMAND_TIMEOUT = 50
_process_limit = asyncio.Semaphore(2)


def _is_approved_url(url: str) -> bool:
    try:
        target = urlsplit(url)
        host = (target.hostname or "").rstrip(".").lower()
        if target.scheme not in {"https", "http"} or not host or target.username or target.password:
            return False
        if target.port not in (None, 80, 443):
            return False
        if len(url) > 2048 or host in {"localhost", "localhost.localdomain"}:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        allowed = READ_DOMAINS | {
            name.strip().lower() for name in os.environ.get("REACH_EXTRA_DOMAINS", "").split(",")
            if name.strip()
        }
        return any(host == d or host.endswith("." + d) for d in allowed)
    except ValueError:
        return False


def _safe_args(channel: str, query: str) -> list[str]:
    if channel not in READABLE_CHANNELS:
        raise ValueError("Unsupported channel")
    if not query or len(query) > MAX_QUERY_CHARS or query.startswith("-") or "\x00" in query:
        raise ValueError("Invalid search query")
    return [channel, "search", query]


async def _run_reach(args: list[str]) -> dict:
    async with _process_limit:
        executable = os.environ.get("AGENT_REACH_BIN", "agent-reach")
        try:
            proc = await asyncio.create_subprocess_exec(
                executable, *args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            return {"ok": False, "error": {"code": "CLI_NOT_INSTALLED"}}
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=COMMAND_TIMEOUT)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return {"ok": False, "error": {"code": "TIMEOUT"}}
        if len(stdout) > MAX_OUTPUT_BYTES:
            return {"ok": False, "error": {"code": "OUTPUT_LIMIT"}}
        try:
            result = json.loads(stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return {"ok": False, "error": {"code": "CLI_INVALID_OUTPUT"}}
        if not isinstance(result, dict):
            return {"ok": False, "error": {"code": "CLI_INVALID_OUTPUT"}}
        return result


class BearerGate:
    """Require bearer authentication even for MCP discovery and GET."""

    def __init__(self, app, key: str):
        if len(key) < 32:
            raise ValueError("REACH_BRIDGE_TOKEN must have at least 32 characters")
        self.app = app
        self.expected = ("Bearer " + key).encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            provided = headers.get(b"authorization", b"")
            if not hmac.compare_digest(provided, self.expected):
                body = b'{"error":"unauthorized"}'
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def build_app():
    from mcp.server import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings

    token = os.environ.get("REACH_BRIDGE_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("Set random REACH_BRIDGE_TOKEN (32+ characters) before starting")
    hosts = [h.strip() for h in os.environ.get(
        "REACH_BRIDGE_HOSTS", "localhost:*,127.0.0.1:*,[::1]:*"
    ).split(",") if h.strip()]

    server = MCPServer("Agent Reach — read only")

    @server.tool()
    async def channels() -> dict:
        """List Agent Reach channels and supported actions."""
        return await _run_reach(["channels"])

    @server.tool()
    async def doctor() -> dict:
        """Inspect installed Agent Reach channel status."""
        return await _run_reach(["doctor"])

    @server.tool()
    async def read_url(url: str) -> dict:
        """Read an approved public-platform URL."""
        if not _is_approved_url(url):
            return {"ok": False, "error": {"code": "URL_NOT_ALLOWED"}}
        return await _run_reach(["read", url])

    @server.tool()
    async def search(channel: str, query: str) -> dict:
        """Search via an Agent Reach CLI channel."""
        try:
            args = _safe_args(channel, query)
        except ValueError:
            return {"ok": False, "error": {"code": "BAD_INPUT"}}
        return await _run_reach(args)

    transport = server.streamable_http_app(
        json_response=True, stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=[],
        ),
    )
    return BearerGate(transport, token)


app = build_app()
