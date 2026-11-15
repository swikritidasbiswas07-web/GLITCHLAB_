"""GLITCHLAB_ Round 3 isolated workspace API (local integration slice).

This router intentionally uses /workspaces/... paths and does NOT change the
legacy /drafts, /rules, /sources or /governance endpoints. Until all old routes
are migrated or disabled, this is not complete tenant isolation.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from auth import bearer, lookup_token
from workspace_core import (AccessDenied, WorkspaceConflict, WorkspaceNotFound,
                            create_workspace, initialize as init_core,
                            list_workspaces, require_action, set_member_role)
from workspace_workflow import (initialize as init_workflow, evaluate, run_detail, decide, review_history, ReviewConflict)
from workspace_data import (NotFound, add_draft, get_draft, initialize as init_data,
                            list_drafts, revise_draft, list_sources, get_source,
                            list_rules, list_unit_cases, RevisionConflict)

router = APIRouter(prefix='/workspaces', tags=['Isolated Workspaces — Round 3'])
_db: Callable[[], Any] | None = None


def install(db_provider: Callable[[], Any]) -> APIRouter:
    global _db
    _db = db_provider
    with _db() as con:
        init_core(con)
        init_data(con)
        init_workflow(con)
    return router


def actor_id(request: Request) -> str:
    """Derive actor solely from server-verified bearer token; never from a body or role picker."""
    token = bearer(request.headers.get('authorization', ''))
    user = lookup_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail='Sign in to access this workspace.')
    return user['id']


def fail(exc: Exception) -> None:
    if isinstance(exc, (AccessDenied,)):
        raise HTTPException(403, 'Not authorized for this workspace action') from exc
    if isinstance(exc, (NotFound, WorkspaceNotFound)):
        raise HTTPException(404, 'Resource not found') from exc
    if isinstance(exc, (ReviewConflict, RevisionConflict)):
        raise HTTPException(409, str(exc)) from exc
    if isinstance(exc, WorkspaceConflict):
        raise HTTPException(409, str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(422, str(exc)) from exc
    raise exc


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class MemberIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern=r'^(admin|editor|reviewer|creator)$')


class DraftIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    channel: str = Field(pattern=r'^(social|email|website|general)$')
    content: str = Field(min_length=1, max_length=12000)


class RevisionIn(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    expected_version: int | None = Field(default=None, ge=1)


@router.get('')
def my_workspaces(request: Request):
    uid = actor_id(request)
    with _db() as con:
        return list_workspaces(con, user_id=uid)


@router.post('', status_code=201)
def new_workspace(body: WorkspaceIn, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return create_workspace(con, creator_id=uid, name=body.name)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/members')
def members(workspace_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            require_action(con, user_id=uid, workspace_id=workspace_id, action='workspace:read')
            return [dict(r) for r in con.execute('''
                SELECT m.user_id,u.display_name,u.email,m.role,m.joined_at
                FROM gl_memberships m JOIN auth_users u ON u.id=m.user_id
                WHERE m.workspace_id=? ORDER BY u.display_name,u.id
            ''', (workspace_id,))]
        except Exception as exc:
            fail(exc)


@router.put('/{workspace_id}/members')
def change_member(workspace_id: str, body: MemberIn, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            set_member_role(con, acting_user_id=uid, workspace_id=workspace_id,
                            member_user_id=body.user_id, role=body.role)
            return {'ok': True}
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/drafts')
def drafts(workspace_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return list_drafts(con, actor_id=uid, workspace_id=workspace_id)
        except Exception as exc:
            fail(exc)


@router.post('/{workspace_id}/drafts', status_code=201)
def create_draft(workspace_id: str, body: DraftIn, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return add_draft(con, actor_id=uid, workspace_id=workspace_id,
                             title=body.title, channel=body.channel, content=body.content)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/drafts/{draft_id}')
def draft_detail(workspace_id: str, draft_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return get_draft(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id)
        except Exception as exc:
            fail(exc)


@router.post('/{workspace_id}/drafts/{draft_id}/revisions', status_code=201)
def create_revision(workspace_id: str, draft_id: str, body: RevisionIn, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return revise_draft(con, actor_id=uid, workspace_id=workspace_id,
                                draft_id=draft_id, content=body.content, expected_version=body.expected_version)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/sources')
def sources(workspace_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return list_sources(con, actor_id=uid, workspace_id=workspace_id)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/sources/{source_id}')
def source_detail(workspace_id: str, source_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return get_source(con, actor_id=uid, workspace_id=workspace_id, source_id=source_id)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/rules')
def rules(workspace_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return list_rules(con, actor_id=uid, workspace_id=workspace_id)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/unit-cases')
def unit_cases(workspace_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return list_unit_cases(con, actor_id=uid, workspace_id=workspace_id)
        except Exception as exc:
            fail(exc)


class ReviewIn(BaseModel):
    decision: str = Field(pattern=r'^(approved|changes_requested)$')
    comment: str = Field(default='', max_length=1000)


@router.post('/{workspace_id}/drafts/{draft_id}/run')
def test_draft(workspace_id: str, draft_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return evaluate(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/runs/{run_id}')
def get_run(workspace_id: str, run_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return run_detail(con, actor_id=uid, workspace_id=workspace_id, run_id=run_id)
        except Exception as exc:
            fail(exc)


@router.post('/{workspace_id}/drafts/{draft_id}/reviews', status_code=201)
def post_review(workspace_id: str, draft_id: str, body: ReviewIn, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return decide(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id,
                          decision=body.decision, comment=body.comment)
        except Exception as exc:
            fail(exc)


@router.get('/{workspace_id}/drafts/{draft_id}/reviews')
def reviews(workspace_id: str, draft_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return review_history(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id)
        except Exception as exc:
            fail(exc)


# Build 04J: actual authenticated, workspace-scoped activity and version comparison.
from tracebook import timeline as tracebook_timeline, compare_versions as tracebook_compare

@router.get('/{workspace_id}/drafts/{draft_id}/activity')
def draft_activity(workspace_id: str, draft_id: str, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return tracebook_timeline(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id)
        except Exception as exc:
            fail(exc)

@router.get('/{workspace_id}/drafts/{draft_id}/compare')
def draft_compare(workspace_id: str, draft_id: str, before: int, after: int, request: Request):
    uid = actor_id(request)
    with _db() as con:
        try:
            return tracebook_compare(con, actor_id=uid, workspace_id=workspace_id, draft_id=draft_id, before=before, after=after)
        except Exception as exc:
            fail(exc)
