"""配流验算单编排层测试：SQLite 内存库，不依赖 MySQL/Redis/网络。

FOR UPDATE 行锁在 MySQL 上生效，SQLite 方言忽略该子句；并发正确性靠
upload/seal 统一走 _locked_sheet 串行化，这里用顺序调用复现两种交错结果。
"""
import unittest
import _bootstrap  # noqa: F401  统一临时库与建表，须先于其他后端导入
from sqlalchemy import select,func
from src.config.database import Session

from fastapi import HTTPException
from src.models import NetworkDataset,TransferArc,OutageScenario,NetworkRun,FlowSheet,FlowShard
from src.schemas.flowsheet import SheetInput,ShardInput,ShardEntry
from src.services import flowsheets as svc
from src.utils.time import now

ARCS=[
 ("e1","S","A",5),("e2","S","B",3),("e3","A","T",4),("e4","B","T",3),
 ("e5","A","B",2),("e6","B","A",2),("e7","S","A",2),
]
def seed_fixture():
 with Session() as db:
  if db.get(NetworkDataset,"db-d1"):return
  db.add(NetworkDataset(id="db-d1",name="编排测试网络",source="test",nodes=[{"node_id":n,"label":n,"x":0,"y":0} for n in ["S","A","B","T"]],created_at=now()))
  for aid,u,v,cap in ARCS:
   db.add(TransferArc(id="db-id-"+aid,dataset_id="db-d1",arc_id=aid,source=u,target=v,capacity=cap,travel_minutes=1,created_at=now()))
  snap=[{"arc_id":aid,"source":u,"target":v,"capacity":cap,"travel_minutes":1} for aid,u,v,cap in ARCS]
  db.add(OutageScenario(id="db-sc1",name="编排停用方案",dataset_id="db-d1",source_node="S",sink_node="T",disabled_arc_ids=[],arc_snapshot=snap,created_at=now()))
  db.add(NetworkRun(id="db-run1",scenario_id="db-sc1",status="completed",result={},error="",created_at=now()))
  db.commit()

def shard(index,pairs):
 return ShardInput(shard_index=index,entries=[ShardEntry(arc_id=a,amount=v) for a,v in pairs])

class OrchestrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):seed_fixture()
 def test_01_create_and_upload_dedup(self):
  with Session() as db:
   sheet=svc.create_sheet(db,SheetInput(name="单A",run_id="db-run1",expected_shards=2))
   sid=sheet["id"]
   r1=svc.upload_shard(db,sid,shard(0,[("e1",3),("e3",3)]))
   self.assertFalse(r1["deduplicated"])
   # 同号同文重试：幂等，不重复写入
   r1b=svc.upload_shard(db,sid,shard(0,[("e3",3),("e1",3)]))
   self.assertTrue(r1b["deduplicated"])
   self.assertEqual(db.scalar(select(func.count()).select_from(FlowShard).where(FlowShard.sheet_id==sid)),1)
 def test_02_same_index_different_content_rejected(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单B",run_id="db-run1",expected_shards=2))["id"]
   svc.upload_shard(db,sid,shard(0,[("e1",2)]))
   with self.assertRaises(HTTPException) as c:svc.upload_shard(db,sid,shard(0,[("e1",3)]))
   self.assertEqual(c.exception.status_code,409)
 def test_03_cross_shard_overlap_and_unknown_rejected(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单C",run_id="db-run1",expected_shards=2))["id"]
   svc.upload_shard(db,sid,shard(0,[("e1",2)]))
   with self.assertRaises(HTTPException) as c:svc.upload_shard(db,sid,shard(1,[("e1",1),("e3",1)]))
   self.assertEqual(c.exception.status_code,409)
   with self.assertRaises(HTTPException) as c:svc.upload_shard(db,sid,shard(2,[("ex",1)]))
   self.assertEqual(c.exception.status_code,422)
 def test_04_seal_waits_for_all_shards_then_passes(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单D",run_id="db-run1",expected_shards=2))["id"]
   svc.upload_shard(db,sid,shard(0,[("e1",3),("e3",3),("e5",1)]))
   with self.assertRaises(HTTPException) as c:svc.seal_sheet(db,sid)
   self.assertEqual(c.exception.status_code,409)
   self.assertEqual(db.get(FlowSheet,sid).status,"open")
   # 中断后接着补传第二片（含反向边构成独立循环 e5/e6 各1）
   svc.upload_shard(db,sid,shard(1,[("e2",2),("e4",2),("e6",1)]))
   sealed=svc.seal_sheet(db,sid)
   self.assertEqual(sealed["status"],"passed")
   self.assertTrue(sealed["sealed_at"])
   self.assertEqual(sealed["result"]["delivered"],5)
   self.assertEqual(sealed["result"]["cycle_flow_total"],1)
   self.assertEqual(len(sealed["result"]["cycles"]),1)
   # 逐边合计还原
   for row in sealed["result"]["arc_reconciliation"]:
    self.assertEqual(row["amount"],row["decomposed_amount"])
 def test_05_missing_edges_count_as_zero(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单E",run_id="db-run1",expected_shards=1))["id"]
   # 只传 e1/e3，其余边缺省按零；这本身守恒，送达量3
   svc.upload_shard(db,sid,shard(0,[("e1",3),("e3",3)]))
   sealed=svc.seal_sheet(db,sid)
   self.assertEqual(sealed["status"],"passed")
   self.assertEqual(sealed["result"]["nonzero_arc_count"],2)
 def test_06_sealed_sheet_rejects_rewrite_and_reseal(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单F",run_id="db-run1",expected_shards=1))["id"]
   svc.upload_shard(db,sid,shard(0,[("e2",1),("e4",1)]));svc.seal_sheet(db,sid)
   with self.assertRaises(HTTPException) as c:svc.upload_shard(db,sid,shard(1,[("e1",1)]))
   self.assertEqual(c.exception.status_code,409)
   with self.assertRaises(HTTPException) as c:svc.seal_sheet(db,sid)
   self.assertEqual(c.exception.status_code,409)
 def test_07_failure_lists_differences_and_publishes_no_decomposition(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单G",run_id="db-run1",expected_shards=1))["id"]
   # 超容量且不守恒
   svc.upload_shard(db,sid,shard(0,[("e1",9)]))
   sealed=svc.seal_sheet(db,sid)
   self.assertEqual(sealed["status"],"failed")
   self.assertEqual(sealed["result"],{})
   self.assertIn("capacity_violations",sealed["differences"]["differences"])
   self.assertIn("conservation_violations",sealed["differences"]["differences"])
 def test_08_concurrent_interleavings(self):
  # 交错一：封单先成功，后到补传必须被拒（封单内容为准）。
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单H",run_id="db-run1",expected_shards=0))["id"]
   svc.upload_shard(db,sid,shard(0,[("e1",1),("e3",1)]));svc.seal_sheet(db,sid)
   with self.assertRaises(HTTPException) as c:svc.upload_shard(db,sid,shard(1,[("e2",1)]))
   self.assertEqual(c.exception.status_code,409)
  # 交错二：补传先落库，封单在锁后看到完整两片并按完整内容验算。
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单I",run_id="db-run1",expected_shards=2))["id"]
   svc.upload_shard(db,sid,shard(0,[("e1",2),("e3",2)]))
   svc.upload_shard(db,sid,shard(1,[("e2",2),("e4",2)]))
   sealed=svc.seal_sheet(db,sid)
   self.assertEqual(sealed["status"],"passed");self.assertEqual(sealed["received_shards"],2)
 def test_09_detail_payload_and_unknown_run(self):
  with Session() as db:
   sid=svc.create_sheet(db,SheetInput(name="单J",run_id="db-run1",expected_shards=1))["id"]
   svc.upload_shard(db,sid,shard(0,[("e7",1),("e3",1)]))
   detail=svc.sheet_detail(db,sid)
   self.assertEqual(detail["arc_count"],len(ARCS));self.assertEqual(detail["scenario_name"],"编排停用方案")
   self.assertEqual(detail["shards"][0]["entry_count"],2)
   with self.assertRaises(HTTPException) as c:svc.create_sheet(db,SheetInput(name="单K",run_id="nope"))
   self.assertEqual(c.exception.status_code,404)

class SeedIdempotencyTests(unittest.TestCase):
 def test_seed_twice_keeps_single_demo_sheet(self):
  import scripts.seed_demo as seed_mod
  seed_mod.seed();seed_mod.seed()
  with Session() as db:
   sheet=db.get(FlowSheet,"demo-sheet")
   self.assertEqual(sheet.status,"passed")
   self.assertEqual(sheet.expected_shards,2);self.assertEqual(sheet.received_shards,2)
   self.assertGreaterEqual(len(sheet.result["cycles"]),1)
   self.assertEqual(db.scalar(select(func.count()).select_from(FlowShard).where(FlowShard.sheet_id=="demo-sheet")),2)
   # 再跑一次幂等种子，演示单与其分片都不重复
   seed_mod.seed()
   self.assertEqual(db.scalar(select(func.count()).select_from(FlowSheet).where(FlowSheet.id=="demo-sheet")),1)
   self.assertEqual(db.scalar(select(func.count()).select_from(FlowShard).where(FlowShard.sheet_id=="demo-sheet")),2)

if __name__=="__main__":
 unittest.main(verbosity=2)
