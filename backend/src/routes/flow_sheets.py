from fastapi import APIRouter,Depends
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import FlowSheet
from src.schemas.flowsheet import SheetInput,ShardInput
from src.services import flowsheets as service
from src.utils.serialization import rows
router=APIRouter(prefix="/flow-sheets")
@router.get("")
def listing(db=Depends(db_session),user=Depends(current_user)):return rows(db.scalars(select(FlowSheet).order_by(FlowSheet.created_at.desc())))
@router.post("")
def create(payload:SheetInput,db=Depends(db_session),user=Depends(writer)):return service.create_sheet(db,payload)
@router.get("/{sheet_id}")
def detail(sheet_id:str,db=Depends(db_session),user=Depends(current_user)):return service.sheet_detail(db,sheet_id)
@router.post("/{sheet_id}/shards")
def upload(sheet_id:str,payload:ShardInput,db=Depends(db_session),user=Depends(writer)):return service.upload_shard(db,sheet_id,payload)
@router.post("/{sheet_id}/seal")
def seal(sheet_id:str,db=Depends(db_session),user=Depends(writer)):return service.seal_sheet(db,sheet_id)
