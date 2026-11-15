"""Local PostgreSQL preview: workspace-scoped policy authoring.

Register this router ONLY on the local pg_app test service. The existing
workspace_data.add_rule function performs server-side admin authorization.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation

from workspace_api import actor_id, fail
from workspace_data import add_rule
from pg_compat import pg_db

router = APIRouter(prefix='/workspaces', tags=['Workspace Policy Vault'])


class RuleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    category: str = Field(pattern=r'^(fact|claim|tone|terminology)$')
    title: str = Field(min_length=2, max_length=120)
    pattern: str = Field(min_length=1, max_length=160)
    replacement: str = Field(default='', max_length=250)


@router.post('/{workspace_id}/rules', status_code=201)
def create_workspace_rule(workspace_id: str, body: RuleCreate, request: Request):
    uid = actor_id(request)
    try:
        with pg_db() as con:
            result = add_rule(con, actor_id=uid, workspace_id=workspace_id,
                              code=body.code.strip(), category=body.category,
                              title=body.title.strip(), pattern=body.pattern,
                              replacement=body.replacement)
        return result
    except UniqueViolation as exc:
        raise HTTPException(409, 'A rule with this code already exists in this workspace.') from exc
    except Exception as exc:
        fail(exc)
