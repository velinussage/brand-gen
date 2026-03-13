# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by opening a private issue or contacting the maintainers directly.

Do **not** open a public issue for security vulnerabilities.

## Scope

brand-gen is a local CLI tool that calls external APIs (Replicate, optionally Anthropic/OpenAI for LLM routing). Security considerations:

- **API keys**: Stored in `.env` (gitignored). Never committed to the repo.
- **Generated assets**: Stored locally. No automatic upload or sharing.
- **MCP server**: Runs over stdio (stdin/stdout). No network listener by default.
- **Agent browser**: If used for screenshot capture, runs a local headless browser. No remote access.

## Supported Versions

Only the latest release is supported with security updates.
