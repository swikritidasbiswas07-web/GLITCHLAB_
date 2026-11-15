"""Workspace-authorized Protocol Studio / RippleMap endpoints."""
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel, Field
import workspace_api
from workspace_core import AccessDenied
import protocol_studio as service
import regression_workbench as workbench

router=APIRouter(prefix='/workspaces/{workspace_id}/protocol',tags=['Protocol Studio and RippleMap'])

class PublishIn(BaseModel):
    note:str=Field(min_length=1,max_length=500)
    expected_hash:str=Field(min_length=64,max_length=64,pattern=r'^[0-9a-f]{64}$')

def _call(request,fn,**kwargs):
    uid=workspace_api.actor_id(request)
    with workspace_api._db() as con:
        try:return fn(con,actor_id=uid,**kwargs)
        except AccessDenied as exc:raise HTTPException(403,'Not authorized for this workspace action') from exc
        except service.ProtocolConflict as exc:raise HTTPException(409,str(exc)) from exc
        except workbench.CaseNotFound as exc:raise HTTPException(404,str(exc)) from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@router.get('/preview')
def preview(workspace_id:str,request:Request):
    return _call(request,service.preview,workspace_id=workspace_id)

@router.get('/releases')
def releases(workspace_id:str,request:Request):
    return _call(request,service.history,workspace_id=workspace_id)

@router.get('/impact')
def impact(workspace_id:str,request:Request):
    return _call(request,service.impact,workspace_id=workspace_id)

@router.post('/releases',status_code=201)
def publish(workspace_id:str,body:PublishIn,request:Request):
    return _call(request,service.publish,workspace_id=workspace_id,**body.model_dump())


# Build 05J.1: test cases use existing gl_guideline_cases storage.
class RegressionCaseIn(BaseModel):
    rule_id: str=Field(min_length=1,max_length=128)
    channel: str=Field(default='social',min_length=1,max_length=60)
    sample: str=Field(min_length=1,max_length=4000)
    expected_match: bool
    note: str=Field(default='',max_length=500)

@router.get('/cases')
def regression_cases(workspace_id:str,request:Request):
    return _call(request,workbench.list_cases,workspace_id=workspace_id)

@router.post('/cases',status_code=201)
def add_regression_case(workspace_id:str,body:RegressionCaseIn,request:Request):
    return _call(request,workbench.create_case,workspace_id=workspace_id,**body.model_dump())

@router.delete('/cases/{case_id}')
def remove_regression_case(workspace_id:str,case_id:str,request:Request):
    return _call(request,workbench.delete_case,workspace_id=workspace_id,case_id=case_id)
