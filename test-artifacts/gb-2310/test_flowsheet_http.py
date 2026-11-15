"""HTTP 路由冒烟：FastAPI TestClient + SQLite，验证鉴权、校验与封单语义。"""
import unittest
import _bootstrap  # noqa: F401  统一临时库与建表，须先于其他后端导入
from fastapi.testclient import TestClient
from src.config.database import Session
from src.models import NetworkDataset,TransferArc,OutageScenario,NetworkRun
from src.utils.security import hash_password,token
from src.models import User
from src.utils.time import now
from src.main import app

def fixture():
 with Session() as db:
  if db.get(NetworkDataset,"http-d1"):return
  if not db.get(User,"analyst"):db.add(User(id="analyst",email="a@x.demo",password=hash_password("pw"),role="analyst"))
  if not db.get(User,"viewer"):db.add(User(id="viewer",email="v@x.demo",password=hash_password("pw"),role="viewer"))
  db.add(NetworkDataset(id="http-d1",name="HTTP网络",source="t",nodes=[{"node_id":n,"label":n,"x":0,"y":0} for n in ["S","A","T"]],created_at=now()))
  for aid,u,v,c in [("e1","S","A",4),("e2","A","T",4)]:
   db.add(TransferArc(id="http-i-"+aid,dataset_id="http-d1",arc_id=aid,source=u,target=v,capacity=c,travel_minutes=1,created_at=now()))
  snap=[{"arc_id":"e1","source":"S","target":"A","capacity":4,"travel_minutes":1},{"arc_id":"e2","source":"A","target":"T","capacity":4,"travel_minutes":1}]
  db.add(OutageScenario(id="http-sc1",name="HTTP方案",dataset_id="http-d1",source_node="S",sink_node="T",disabled_arc_ids=[],arc_snapshot=snap,created_at=now()))
  db.add(NetworkRun(id="http-run1",scenario_id="http-sc1",status="completed",result={},error="",created_at=now()))
  db.commit()
fixture()
client=TestClient(app)
AUTH={"Authorization":"Bearer "+token(Session().get(User,"analyst"))}
VAUTH={"Authorization":"Bearer "+token(Session().get(User,"viewer"))}

class HttpTests(unittest.TestCase):
 def test_01_auth_required_and_viewer_forbidden(self):
  self.assertEqual(client.post("/flow-sheets",json={"name":"x","run_id":"http-run1"}).status_code,401)
  r=client.post("/flow-sheets",json={"name":"只读单","run_id":"http-run1"},headers=VAUTH)
  self.assertEqual(r.status_code,403)
 def test_02_full_lifecycle_and_seal_guard(self):
  r=client.post("/flow-sheets",json={"name":"HTTP验算单","run_id":"http-run1","expected_shards":1},headers=AUTH)
  self.assertEqual(r.status_code,200,r.text);sid=r.json()["id"]
  # 布尔运量被 422 拒绝
  r=client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":0,"entries":[{"arc_id":"e1","amount":True}]},headers=AUTH)
  self.assertEqual(r.status_code,422)
  # 正常分片
  r=client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":0,"entries":[{"arc_id":"e1","amount":2},{"arc_id":"e2","amount":2}]},headers=AUTH)
  self.assertEqual(r.status_code,200);self.assertFalse(r.json()["deduplicated"])
  # 重试同文（换顺序）幂等
  r=client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":0,"entries":[{"arc_id":"e2","amount":2},{"arc_id":"e1","amount":2}]},headers=AUTH)
  self.assertTrue(r.json()["deduplicated"])
  # 同号异文拒绝
  r=client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":0,"entries":[{"arc_id":"e1","amount":3}]},headers=AUTH)
  self.assertEqual(r.status_code,409)
  # 封单通过
  r=client.post(f"/flow-sheets/{sid}/seal",headers=AUTH)
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()["status"],"passed")
  self.assertEqual(r.json()["result"]["delivered"],2)
  # 封单后补传/再封均拒绝
  self.assertEqual(client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":1,"entries":[]},headers=AUTH).status_code,409)
  self.assertEqual(client.post(f"/flow-sheets/{sid}/seal",headers=AUTH).status_code,409)
  # 回看明细含分片与对账
  d=client.get(f"/flow-sheets/{sid}",headers=AUTH).json()
  self.assertEqual(d["shards"][0]["entry_count"],2);self.assertEqual(d["arc_count"],2)
  self.assertEqual(client.get("/flow-sheets",headers=AUTH).status_code,200)
 def test_03_failed_seal_returns_differences(self):
  sid=client.post("/flow-sheets",json={"name":"失败单","run_id":"http-run1","expected_shards":1},headers=AUTH).json()["id"]
  client.post(f"/flow-sheets/{sid}/shards",json={"shard_index":0,"entries":[{"arc_id":"e1","amount":4}]},headers=AUTH)
  r=client.post(f"/flow-sheets/{sid}/seal",headers=AUTH).json()
  self.assertEqual(r["status"],"failed");self.assertEqual(r["result"],{})
  self.assertIn("conservation_violations",r["differences"]["differences"])

if __name__=="__main__":
 unittest.main(verbosity=2)
