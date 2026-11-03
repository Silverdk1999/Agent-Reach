# Agent Reach → ChatGPT MCP bridge (read-only)

This folder contains an **authenticated MCP Streamable HTTP bridge** for the actual Agent Reach CLI, from the same repository. It is not a live deployment or a replacement implementation.

## Supported tools

- channels: list available CLI channels
- doctor: inspect channel status
- read_url: read an allowed public-platform URL
- search: search an approved channel

There are **no** commands for installing/updating software, executing arbitrary shell commands, logging into sites, reading local cookies, or modifying accounts.

## Prepare the execution host

1. Install **Agent Reach 1.6+** from the owner's fork, following its docs/install.md. Confirm that **agent-reach version** and **agent-reach doctor** work in the host's terminal.
2. Make a separate Python 3.10+ environment for the bridge and install:

   python -m pip install -r requirements.txt

3. Set **REACH_BRIDGE_TOKEN** to a random secret with at least 32 characters using your host's secret manager. Do not commit or paste it into messages.
4. For local testing, start in this folder:

   uvicorn bridge:app --host 127.0.0.1 --port 8000

5. Test that requests without Authorization: Bearer <token> to /mcp receive HTTP 401. The MCP client must send the token on every request.

Optional: specify **AGENT_REACH_BIN** to use a custom Agent Reach CLI executable, **REACH_EXTRA_DOMAINS** to append approved public domain names, and **REACH_BRIDGE_HOSTS** to set the exact publicly served Host header names (for example **reach.example.com,reach.example.com:***).

## Connecting from ChatGPT

ChatGPT's cloud cannot access localhost. Run this bridge on an actual execution host, expose it only behind a secure HTTPS gateway using a stable domain and authentication, and use its verified **https://YOUR_HOST/mcp** endpoint when configuring the ChatGPT plugin. The endpoint is **not configured** and ChatGPT cannot use it until deployment and authorized connection are complete.

Login-dependent channels work only after the user separately logs in on the execution host using Agent Reach's own user-controlled login flow. No browser cookies, tokens, or sessions are copied by this bridge.

## Security boundaries

- Bearer token required for every HTTP MCP request, including discovery.
- Strict CLI argument construction, channel and URL allowlists, time and output limits.
- No shell interpolation, no CLI setup/login/update or browser credential actions.
- Host-header allowlist (including DNS rebinding protection). Set REACH_BRIDGE_HOSTS for the exact reverse proxy hostname; leave the default loopback-only for local testing.
- For public hosting: use TLS, rate limits, unprivileged execution and outbound firewall rules. Domain allowlisting here is not sufficient to guarantee safety against redirects or private-IP DNS resolution inside the upstream CLI.

## Why not Gotweb?

**Gotweb** is a web interface for displaying Git repositories (superseded by Gotwebd). It does not run Agent Reach CLI or implement the MCP protocol. It can serve as a repository viewer, but not as the execution host for this bridge.
