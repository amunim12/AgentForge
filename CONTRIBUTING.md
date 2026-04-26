# Contributing to AgentForge

Thanks for your interest in improving AgentForge. This document covers the development workflow, coding standards, and what we expect in a pull request.

## Development setup

Follow the **Quick start** in [README.md](README.md) to get the backend and frontend running locally. You will need a `.env` file with valid API keys for any flow that touches an LLM, but the test suite stubs every external dependency, so you can run `pytest` with dummy values.

## Project conventions

### Backend (Python 3.11+)

- **Style**: `ruff` for lint, `black` for formatting (88-col), `mypy --strict` for types.
- **Async-first**: every I/O path (DB, HTTP, LLM) is async. Don't introduce blocking calls inside request handlers or agent code.
- **Settings**: never read `os.environ` from app code. Add the variable to `app.core.config.Settings` so it's validated at startup.
- **Errors**: raise `AgentForgeError` subclasses (`app.core.exceptions`). Constructor messages are internal; the `public_message` class attribute is what reaches the client.
- **Logging**: `structlog.get_logger()` only, never `print`. Include `task_id` on every line in agent code.

### Frontend (TypeScript)

- **Style**: ESLint (`next/core-web-vitals`), Prettier, `tsc --noEmit` clean.
- **Components**: prefer composition over options-bag props. shadcn/ui primitives are local — fork them in `components/ui/` if you need to extend.
- **State**: server state through TanStack Query, ephemeral UI state through Zustand or `useState`. Don't put server data in Zustand.
- **Tailwind**: no dynamic class strings (`bg-${color}` won't survive the JIT). Hoist static classes into a lookup.

### Commits and branches

- Branch off `main`, name the branch after what you're doing (`feat/critic-rubric-weights`, `fix/ws-reconnect-loop`).
- Conventional Commits encouraged: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- Keep commits focused. A reviewer should be able to read each one in isolation.

## Running checks locally

```bash
# Backend
cd backend
ruff check . && black --check . && mypy app
pytest --cov=app --cov-fail-under=80

# Frontend
cd frontend
pnpm lint && pnpm type-check && pnpm build
```

CI runs the same gates. PRs that don't pass them won't be merged.

## Pull request checklist

Before opening a PR, confirm:

- [ ] Tests cover the behavior change (not just the lines).
- [ ] No secrets, API keys, or `.env` files in the diff.
- [ ] User-facing changes are reflected in the README if they change setup or configuration.
- [ ] No new top-level dependencies unless justified in the PR description.
- [ ] If you touched an agent, the public schema (`app.schemas.agent`) still validates real outputs end-to-end.

## Adding a new tool to the executor

1. Create `backend/app/tools/your_tool.py` exposing a `@tool`-decorated callable.
2. Truncate large outputs (see `_truncate` in `code_executor.py`).
3. Wrap external errors in a friendly string return — never raise from inside a tool.
4. Register it in `app.agents.executor.run_executor`'s `tools = [...]` list.
5. Add a unit test under `backend/tests/test_tools/` that mocks the upstream client.

## Adding a new agent

LangGraph nodes live in `app.agents.orchestrator`. To add one:

1. Implement the agent function (`run_*`) in its own module under `app/agents/`. Stream output via `publish_task_update`.
2. Add a node + edge in `build_graph()`.
3. Define any new event types in `app.schemas.agent.EventType`.
4. Update the frontend `useTaskStream` hook and add a card under `components/agents/`.
5. Test with both `_build_llm` patched and the orchestrator-level happy path.

## Reporting bugs

Open a GitHub issue with:

- What you expected vs. what happened
- Reproduction steps (smallest possible)
- Backend logs (with `task_id` if applicable)
- Browser console output for frontend issues

For security issues, see [SECURITY.md](SECURITY.md) — please don't open public issues for those.

## License

By contributing, you agree your contributions are licensed under the MIT License.
