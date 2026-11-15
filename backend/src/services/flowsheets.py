import uuid
from fastapi import HTTPException
from sqlalchemy import select
from src.models import FlowSheet,FlowShard,NetworkRun,OutageScenario,NetworkDataset
from src.services import flowverify
from src.utils.time import now
from src.utils.serialization import serialize

def _context(db,run_id):
 run=db.get(NetworkRun,run_id)
 if not run:raise HTTPException(404,"推演不存在，无法绑定验算单")
 scenario=db.get(OutageScenario,run.scenario_id)
 if not scenario:raise HTTPException(404,"推演缺少停用方案快照")
 dataset=db.get(NetworkDataset,scenario.dataset_id)
 if not dataset:raise HTTPException(404,"推演缺少网络节点快照")
 return run,scenario,dataset

def create_sheet(db,payload):
 run,scenario,dataset=_context(db,payload.run_id)
 if db.scalar(select(FlowSheet).where(FlowSheet.name==payload.name)):raise HTTPException(409,"验算单名称已存在")
 item=FlowSheet(id=str(uuid.uuid4()),name=payload.name,run_id=payload.run_id,expected_shards=payload.expected_shards,received_shards=0,status="open",result={},differences={},error="",created_at=now(),sealed_at="")
 db.add(item);db.commit();return serialize(item)

def _locked_sheet(db,sheet_id):
 """SELECT ... FOR UPDATE 行锁；MySQL 原生支持，SQLite 测试下降级为普通读取。"""
 item=db.get(FlowSheet,sheet_id,with_for_update=True)
 if not item:raise HTTPException(404,"验算单不存在")
 return item

def _require_open(item):
 if item.status!="open":raise HTTPException(409,"验算单已封单，拒绝任何改写")

def upload_shard(db,sheet_id,payload):
 item=_locked_sheet(db,sheet_id);_require_open(item)
 run,scenario,dataset=_context(db,item.run_id)
 known={a["arc_id"] for a in scenario.arc_snapshot}
 entries=[e.model_dump() for e in payload.entries]
 incoming={e["arc_id"] for e in entries}
 unknown=sorted(incoming-known)
 if unknown:raise HTTPException(422,"分片含未知边ID："+"、".join(unknown))
 checksum=flowverify.shard_checksum(entries)
 existing=db.scalar(select(FlowShard).where(FlowShard.sheet_id==sheet_id,FlowShard.shard_index==payload.shard_index))
 if existing:
  if existing.checksum==checksum:
   # 同号同文：分片重试，幂等返回，不重复写入。
   db.commit();return {"sheet":serialize(item),"shard":serialize(existing),"deduplicated":True}
  raise HTTPException(409,"同号异文：该分片编号已上传且内容校验码不同，拒绝覆盖")
 cross=db.scalars(select(FlowShard).where(FlowShard.sheet_id==sheet_id)).all()
 used=set()
 for sh in cross:used.update(e["arc_id"] for e in sh.entries)
 overlap=sorted(used & incoming)
 if overlap:raise HTTPException(409,"边已在其他分片出现，每条边只能归属一个分片："+"、".join(overlap))
 shard=FlowShard(id=str(uuid.uuid4()),sheet_id=sheet_id,shard_index=payload.shard_index,checksum=checksum,entries=entries,created_at=now())
 db.add(shard);item.received_shards=1+item.received_shards;db.commit();db.refresh(item);db.refresh(shard)
 return {"sheet":serialize(item),"shard":serialize(shard),"deduplicated":False}

def seal_sheet(db,sheet_id):
 item=_locked_sheet(db,sheet_id);_require_open(item)
 run,scenario,dataset=_context(db,item.run_id)
 shards=list(db.scalars(select(FlowShard).where(FlowShard.sheet_id==sheet_id).order_by(FlowShard.shard_index)))
 if item.expected_shards and item.received_shards!=item.expected_shards:
  raise HTTPException(409,f"分片未收齐：应{item.expected_shards}片，实收{item.received_shards}片")
 indexes=sorted(s.shard_index for s in shards)
 if len(set(indexes))!=len(indexes):raise HTTPException(409,"分片编号重复，无法封单")
 node_ids=[n["node_id"] for n in dataset.nodes]
 amounts=flowverify.aggregate([a["arc_id"] for a in scenario.arc_snapshot],[s.entries for s in shards])
 passed,body,result=flowverify.verify(node_ids,scenario.arc_snapshot,scenario.source_node,scenario.sink_node,scenario.disabled_arc_ids,amounts)
 item.sealed_at=now()
 if passed:
  item.status="passed";item.result=result;item.differences={};item.error=""
 else:
  item.status="failed";item.result={};item.differences=body
 db.commit();db.refresh(item);return serialize(item)

def sheet_detail(db,sheet_id):
 item=db.get(FlowSheet,sheet_id)
 if not item:raise HTTPException(404,"验算单不存在")
 shards=list(db.scalars(select(FlowShard).where(FlowShard.sheet_id==sheet_id).order_by(FlowShard.shard_index)))
 run=db.get(NetworkRun,item.run_id);scenario=db.get(OutageScenario,run.scenario_id) if run else None
 payload=serialize(item)
 payload["shards"]=[{"shard_index":s.shard_index,"checksum":s.checksum,"entry_count":len(s.entries),"created_at":s.created_at} for s in shards]
 payload["arc_count"]=len(scenario.arc_snapshot) if scenario else 0
 payload["scenario_name"]=scenario.name if scenario else ""
 return payload
