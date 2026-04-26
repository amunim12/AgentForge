"""Auth-related middleware helpers.

Route-level authentication is enforced via `Depends(get_current_user)` in
`app/api/deps.py`. This module exposes the HTTPBearer extractor for
endpoints that need to parse tokens outside the dependency chain (e.g.
WebSocket query-string auth).
"""
from __future__ import annotations

from fastapi.security import HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)
