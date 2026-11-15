"""Build 05I workspace-scoped Evidence Atlas HTTP API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import evidence_atlas as ev
import workspace_api
from workspace_core import AccessDenied
from evidence_source_upload import save_text_source

router = APIRouter(prefix='/workspaces/{workspace_id}/evidence-atlas', tags=['Evidence Atlas — ClaimScope'])

class TextSourceIn(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=262144)


@router.post('/sources/text', status_code=201)
def upload_text_source(workspace_id: str, body: TextSourceIn, request: Request):
    return call(request, save_text_source, workspace_id=workspace_id, **body.model_dump())


class EvidenceIn(BaseModel):
    source_id: str = Field(min_length=1)
    quote: str = Field(min_length=1,max_length=4000)
    locator: str = Field(default='',max_length=250)

class ClaimIn(BaseModel):
    draft_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1,max_length=1200)

class LinkIn(BaseModel):
    claim_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    stance: str = Field(pattern='^(supports|contradicts|context)$')
    rationale: str = Field(min_length=4,max_length=1500)


def call(request, func, **kwargs):
    uid = workspace_api.actor_id(request)
    # Respect the active provider configured by pg_app, not a second database.
    with workspace_api._db() as con:
        try:
            return func(con, actor_id=uid, **kwargs)
        except AccessDenied as exc:
            raise HTTPException(403, 'Not authorized for this workspace action') from exc
        except ev.EvidenceMissing as exc:
            raise HTTPException(404, str(exc)) from exc
        except ev.EvidenceConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

@router.get('/sources')
def sources(workspace_id: str, request: Request):
    return call(request,ev.sources,workspace_id=workspace_id)

@router.get('/items')
def items(workspace_id: str, request: Request):
    return call(request,ev.list_evidence,workspace_id=workspace_id)

@router.post('/items',status_code=201)
def add_item(workspace_id: str, body: EvidenceIn, request: Request):
    return call(request,ev.create_evidence,workspace_id=workspace_id,**body.model_dump())

@router.post('/claims',status_code=201)
def add_claim(workspace_id: str, body: ClaimIn, request: Request):
    return call(request,ev.create_claim,workspace_id=workspace_id,**body.model_dump())

@router.get('/drafts/{draft_id}/claims')
def claims(workspace_id: str, draft_id: str, request: Request, version_id: str | None = None):
    return call(request,ev.claim_scope,workspace_id=workspace_id,draft_id=draft_id,version_id=version_id)

@router.post('/links',status_code=201)
def link(workspace_id: str, body: LinkIn, request: Request):
    return call(request,ev.link_evidence,workspace_id=workspace_id,**body.model_dump())

@router.post('/links/{link_id}/attest')
def attest(workspace_id: str, link_id: str, request: Request):
    return call(request,ev.attest_link,workspace_id=workspace_id,link_id=link_id)
