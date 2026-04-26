# Security Policy

## Reporting a vulnerability

**Do not open a public issue for security bugs.**

Email security reports to **security@agentforge.example** (replace with your contact). Include:

- A description of the issue and its impact
- Steps to reproduce, ideally with a minimal proof of concept
- Affected version or commit hash
- Any suggested mitigation

You should expect:

- Acknowledgement within **2 business days**
- A triage decision within **7 days**
- A fix or mitigation plan within **30 days** for confirmed high/critical issues

We will credit reporters in the release notes once a fix ships, unless you ask to remain anonymous.

## Supported versions

AgentForge is pre-1.0. Only the latest commit on `main` receives security fixes.

## Scope

In scope:

- The FastAPI backend (`backend/app/`)
- The Next.js frontend (`frontend/`)
- The Docker images and CI/CD workflows in this repo

Out of scope:

- Third-party LLM providers (Google, Groq, Tavily, E2B) — report to the vendor
- The user's own deployment misconfiguration (open ports, leaked `.env`, etc.)
- Issues that require a compromised user account or local machine

## Threat model

AgentForge runs untrusted user prompts through LLMs that have access to tools. The design assumes:

- **Prompt injection is real.** The executor's tools are sandboxed (E2B for code, scoped Tavily queries for web, in-memory only for the file tool). No tool can read host secrets, write to disk outside the sandbox, or hit internal services.
- **Authenticated, multi-tenant.** Every task is owned by a user; cross-user access is rejected with 404 (not 403, to avoid existence leaks).
- **Secrets stay in `Settings`.** API keys are loaded once at startup from env. They never appear in logs, error responses, or WebSocket events.
- **Errors are sanitized.** `AgentForgeError.public_message` is what the client sees; internal constructor arguments never leak.

## Practices we follow

- **Authentication**: JWT access (30 min) + refresh (7 days), HS256, signed with a 32+ byte `SECRET_KEY`. Refresh tokens are typed and rejected when used as access tokens.
- **Password hashing**: bcrypt via `passlib`, with per-user salts.
- **Rate limiting**: `slowapi` on auth and task-creation endpoints to blunt brute force and abuse.
- **CORS**: explicit allowlist via `ALLOWED_ORIGINS`, no wildcards in production.
- **Input validation**: every request body is a Pydantic model; SQL is parameterized through SQLAlchemy.
- **Code execution**: user code runs in an E2B sandbox with no host filesystem or network access beyond what the sandbox grants.
- **Dependencies**: Dependabot PRs weekly; `pip-audit` and `pnpm audit` run on every push; CodeQL scans Python and TypeScript.
- **Secret scanning**: Gitleaks runs on every push and on a weekly schedule.
- **Container hardening**: backend image runs as non-root with a minimal runtime layer; healthcheck on `/health`.

## What you can do

If you deploy AgentForge:

- Generate a strong `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`).
- Set `DEBUG=false` and a real `ALLOWED_ORIGINS` list.
- Use a managed Postgres for `DATABASE_URL` instead of the SQLite default.
- Rotate API keys regularly and scope them to the minimum permissions the provider supports.
- Front the backend with TLS (e.g. Render, Fly, or your own ingress) — never expose plain HTTP.
