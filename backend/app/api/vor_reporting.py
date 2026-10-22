"""Protected read-only reporting endpoints for synthetic v2."""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.vor import required
from app.services.vor_reporting import report

router=APIRouter(prefix='/vor/reporting', tags=['Fleet reporting'],dependencies=[Depends(required)])

@router.get('/dashboard')
def dashboard(start:str|None=None,end:str|None=None,garage:str|None=None,reason:str|None=None,model:str|None=None,exclude_outliers:bool=False):
    try:
        return report(start,end,garage,reason,model,exclude_outliers)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
