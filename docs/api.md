# API Reference

Base URL (local): `http://localhost:8000`  
Base URL (production): set by your deployment — see `infra/outputs.tf` for the ALB DNS name  
Interactive docs: `{base_url}/api/docs` (Swagger UI)  
OpenAPI schema: `{base_url}/api/openapi.json`

All requests and responses use `application/json`. Timestamps are ISO 8601 UTC strings.

---

## Authentication

AgentForge uses JWT bearer tokens. Include the access token in every protected request:

```
Authorization: Bearer <access_token>
```

Access tokens expire after 30 minutes. Use the refresh endpoint to rotate them without re-logging in.

---

## Endpoints

### Auth

#### `POST /api/auth/register`

Create a new user account.

**Request body:**
```json
{
  "email": "user@example.com",
  "username": "alice",
  "password": "min-8-characters"
}
```

**Response `201`:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**
- `409 Conflict` — email or username already registered

---

#### `POST /api/auth/login`

Exchange credentials for tokens.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Unauthorized` — wrong email or password

---

#### `POST /api/auth/refresh`

Rotate an expired access token using a valid refresh token.

**Request body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response `200`:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:**
- `401 Unauthorized` — refresh token expired or revoked

---

#### `POST /api/auth/logout`

Revoke the current session. Requires `Authorization` header.

**Response `204 No Content`**

---

### Tasks

All task endpoints require `Authorization: Bearer <access_token>`.

#### `POST /api/tasks`

Create a task and immediately kick off the Planner→Executor→Critic pipeline in the background.

**Rate limit:** 10 requests/hour per IP

**Request body:**
```json
{
  "title": "Research vector databases",
  "description": "Compare Pinecone, Weaviate, and Qdrant on indexing speed, query latency, and cost for 10M 1536-dim vectors.",
  "category": "Research"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|------------|
| `title` | string | Yes | max 255 characters |
| `description` | string | Yes | 10–5000 characters; blocked by guardrails if it contains injection patterns |
| `category` | string | No | max 64 characters |

**Response `201`:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Research vector databases",
  "description": "Compare Pinecone, Weaviate, and Qdrant...",
  "category": "Research",
  "status": "pending",
  "user_id": "7c8d9e10-...",
  "planner_output": null,
  "executor_output": null,
  "critic_output": null,
  "final_result": null,
  "iteration_count": 0,
  "critic_score": null,
  "error_message": null,
  "created_at": "2026-05-11T10:00:00Z",
  "updated_at": "2026-05-11T10:00:00Z",
  "completed_at": null
}
```

**Errors:**
- `400 Bad Request` — description blocked by guardrails
- `422 Unprocessable Entity` — schema validation failed (e.g. description too short)
- `429 Too Many Requests` — rate limit exceeded

**Task lifecycle:** The `status` field transitions as the pipeline runs:

```
pending → planning → executing → critiquing → executing (retry) → completed
                                                                 → failed
```

---

#### `GET /api/tasks`

List all tasks belonging to the authenticated user, most recent first.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | 0 | Offset for pagination |
| `limit` | integer | 20 | Page size (1–100) |

**Response `200`:**
```json
[
  {
    "id": "3fa85f64-...",
    "title": "Research vector databases",
    "status": "completed",
    "category": "Research",
    "critic_score": 0.84,
    "created_at": "2026-05-11T10:00:00Z",
    "updated_at": "2026-05-11T10:03:41Z"
  }
]
```

Note: list responses return a summary schema (no agent output fields) to keep payloads small.

---

#### `GET /api/tasks/{task_id}`

Get a single task with full agent outputs.

**Path parameter:** `task_id` — UUID string

**Response `200`:** Full task object (same schema as `POST /api/tasks` response)

**Errors:**
- `404 Not Found` — task doesn't exist or belongs to a different user

---

#### `DELETE /api/tasks/{task_id}`

Delete a task and all its stored agent outputs.

**Response `204 No Content`**

**Errors:**
- `404 Not Found` — task doesn't exist or belongs to a different user

---

#### `POST /api/tasks/{task_id}/cancel`

Cancel a running task. Sets status to `failed` with `error_message: "Cancelled by user"`. If the task is already `completed` or `failed`, this is a no-op.

**Response `200`:** Full task object

**Errors:**
- `404 Not Found` — task doesn't exist or belongs to a different user

---

### WebSocket

#### `WS /api/ws/tasks/{task_id}?token=<access_token>`

Subscribe to live agent events for a task. The JWT is passed as a query parameter because browsers cannot set `Authorization` headers on WebSocket upgrade requests.

**Connection is rejected (code 1008)** if:
- `token` is missing, expired, or invalid
- The task doesn't belong to the authenticated user
- The user account is inactive

**Event schema:**

All events share a `type` field. Additional fields vary by event type:

```json
{ "type": "agent_start", "agent": "planner" }
{ "type": "agent_stream", "agent": "planner", "delta": "Step 1: ..." }
{ "type": "agent_tool_call", "agent": "executor", "tool": "web_search", "input": "vector database benchmark", "output_preview": "Summary: ..." }
{ "type": "agent_done", "agent": "planner", "output": { "steps": [...], "complexity": "medium" } }
{ "type": "agent_start", "agent": "executor" }
{ "type": "agent_done", "agent": "executor", "output": { "formatted_output": "...", "steps_completed": 4 } }
{ "type": "agent_start", "agent": "critic" }
{ "type": "agent_done", "agent": "critic", "output": { "score": 0.84, "strengths": [...], "improvements": [...] } }
{ "type": "task_complete", "result": "# Vector Database Comparison\n...", "score": 0.84 }
{ "type": "task_failed", "error": "Executor LLM call failed" }
```

**Example (JavaScript):**
```javascript
const ws = new WebSocket(
  `ws://localhost:8000/api/ws/tasks/${taskId}?token=${accessToken}`
);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'agent_stream') {
    appendToOutput(data.delta);
  } else if (data.type === 'task_complete') {
    renderFinalResult(data.result, data.score);
  }
};
```

---

### Health

No authentication required.

#### `GET /health/live`

Liveness probe — confirms the process is running.

**Response `200`:**
```json
{ "status": "ok" }
```

#### `GET /health/ready`

Readiness probe — confirms the database and Redis are reachable.

**Response `200`:**
```json
{ "status": "ok", "db": "ok", "redis": "ok" }
```

**Response `503`** if any dependency is unreachable.

---

## Error Response Format

All errors follow a consistent envelope:

```json
{
  "detail": "Human-readable error message",
  "code": "SNAKE_CASE_ERROR_CODE"
}
```

Common error codes:

| Code | HTTP | Meaning |
|------|------|---------|
| `NOT_FOUND` | 404 | Resource doesn't exist or you don't own it |
| `INVALID_TOKEN` | 401 | JWT is missing, expired, or tampered with |
| `UNAUTHORIZED` | 401 | Wrong credentials on login |
| `RATE_LIMITED` | 429 | Request rate limit exceeded |
| `GUARDRAIL_VIOLATION` | 400 | Task description blocked by safety guardrails |
| `VALIDATION_ERROR` | 422 | Request body failed schema validation |
| `INTERNAL_ERROR` | 500 | Unexpected server error (see server logs) |

---

## Pagination

List endpoints accept `skip` and `limit` query parameters. `limit` is capped at 100. Example paginating through all tasks:

```bash
GET /api/tasks?skip=0&limit=20    # page 1
GET /api/tasks?skip=20&limit=20   # page 2
GET /api/tasks?skip=40&limit=20   # page 3
```
