"""配流验算纯函数测试，仅用标准库；不连接数据库/网络。

运行：python3 -m unittest （在 backend 目录下，PYTHONPATH 含 backend）
"""
import unittest
from src.services import flowverify as fv

NODES=["S","A","B","C","T"]
ARCS=[
 {"arc_id":"e1","source":"S","target":"A","capacity":5,"travel_minutes":1},
 {"arc_id":"e2","source":"S","target":"B","capacity":3,"travel_minutes":1},
 {"arc_id":"e3","source":"A","target":"T","capacity":4,"travel_minutes":1},
 {"arc_id":"e4","source":"B","target":"T","capacity":3,"travel_minutes":1},
 {"arc_id":"e5","source":"A","target":"B","capacity":2,"travel_minutes":1},
 {"arc_id":"e6","source":"B","target":"A","capacity":2,"travel_minutes":1},
 {"arc_id":"e7","source":"S","target":"A","capacity":2,"travel_minutes":1},
 {"arc_id":"e8","source":"C","target":"T","capacity":9,"travel_minutes":1},
 {"arc_id":"e9","source":"S","target":"C","capacity":2,"travel_minutes":1},
]
IDS=[a["arc_id"] for a in ARCS]
def amap(pairs):
 d={aid:0 for aid in IDS};d.update(dict(pairs));return d

class ChecksumTests(unittest.TestCase):
 def test_order_independent(self):
  a=[{"arc_id":"e1","amount":2},{"arc_id":"e2","amount":3}]
  b=[{"arc_id":"e2","amount":3},{"arc_id":"e1","amount":2}]
  self.assertEqual(fv.shard_checksum(a),fv.shard_checksum(b))
 def test_value_sensitive(self):
  a=[{"arc_id":"e1","amount":2}];b=[{"arc_id":"e1","amount":3}]
  self.assertNotEqual(fv.shard_checksum(a),fv.shard_checksum(b))

class ReconcileTests(unittest.TestCase):
 def test_capacity_violation_listed(self):
  amounts=amap([("e1",9)])
  passed,diff,cons,delivered=fv.reconcile(NODES,ARCS,"S","T",[],amounts)
  self.assertFalse(passed)
  self.assertEqual(diff["capacity_violations"][0]["arc_id"],"e1")
  self.assertEqual(diff["capacity_violations"][0]["shortfall"],9-5)
 def test_disabled_arc_effective_zero(self):
  amounts=amap([("e1",1)])
  passed,diff,_,_=fv.reconcile(NODES,ARCS,"S","T",["e1"],amounts)
  self.assertFalse(passed);self.assertIn("capacity_violations",diff)
 def test_conservation_violation_delta(self):
  # S->A 5 but A->T only 3, A 囤积 2。
  amounts=amap([("e1",5),("e3",3)])
  passed,diff,_,delivered=fv.reconcile(NODES,ARCS,"S","T",[],amounts)
  self.assertFalse(passed)
  bad={v["node_id"]:v for v in diff["conservation_violations"]}
  self.assertIn("A",bad);self.assertEqual(bad["A"]["delta"],-2)
 def test_unknown_arc(self):
  amounts=amap([("ex",1)])
  passed,diff,_,_=fv.reconcile(NODES,ARCS,"S","T",[],amounts)
  self.assertFalse(passed);self.assertEqual(diff["unknown_arcs"],["ex"])

class DecomposeTests(unittest.TestCase):
 def test_paths_plus_independent_cycle(self):
  # 纯源汇流：S->A->T 3, S->B->T 2
  amounts=amap([("e1",3),("e3",3),("e2",2),("e4",2)])
  passed,_,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertTrue(passed)
  self.assertEqual(result["delivered"],5)
  self.assertEqual(result["path_flow_total"],5)
  self.assertEqual(result["cycle_flow_total"],0)
  self.assertEqual(len(result["cycles"]),0)
  # 逐边分解合计还原
  for aid in IDS:self.assertEqual(result and next(r["decomposed_amount"] for r in result["arc_reconciliation"] if r["arc_id"]==aid),amounts[aid])
 def test_cycle_excluded_from_delivered(self):
  # 在合法源汇流上夹带 A<->B 循环各1
  amounts=amap([("e1",3),("e3",3),("e2",2),("e4",2),("e5",1),("e6",1)])
  passed,_,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertTrue(passed)
  self.assertEqual(result["delivered"],5)
  self.assertEqual(result["path_flow_total"],5)
  self.assertEqual(result["cycle_flow_total"],1)
  self.assertEqual(len(result["cycles"]),1)
  cyc=result["cycles"][0]
  self.assertEqual(sorted(cyc["arc_path"]),["e5","e6"])
  self.assertEqual(cyc["node_path"][0],cyc["node_path"][-1])
  # 循环不计送达：路径总量仍为送达量
  self.assertEqual(sum(p["amount"] for p in result["paths"]),result["delivered"])
 def test_reconstruction_restores_every_amount(self):
  # e1/e7 平行 S->A 共4，e3 满4 入T；e2->B 2、e4 2 入T；e5/e6 反向各2 独立循环。
  amounts=amap([("e1",3),("e7",1),("e3",4),("e2",2),("e4",2),("e5",2),("e6",2)])
  passed,_,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertTrue(passed,msg="应满足守恒并可完全分解")
  self.assertEqual(result["delivered"],6)
  for row in result["arc_reconciliation"]:
   self.assertEqual(row["decomposed_amount"],row["amount"],msg=row["arc_id"])
 def test_parallel_and_reverse_reconciled_separately(self):
  # e1/e7 平行 S->A 共4，e3 满4 入T；e5/e6 反向各1 构成 A<->B 自平衡循环。
  amounts=amap([("e1",2),("e7",2),("e3",4),("e5",1),("e6",1)])
  passed,_,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertTrue(passed)
  pids={tuple(sorted(a["arc_id"] for a in g["arcs"])) for g in result["parallel_groups"]}
  self.assertIn(("e1","e7"),pids)
  rev=result["reverse_pairs"][0]
  self.assertEqual({x["arc_id"] for x in rev["forward"]+rev["backward"]},{"e5","e6"})
 def test_failure_publishes_no_decomposition(self):
  amounts=amap([("e1",5)]) # 不守恒
  passed,body,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertFalse(passed);self.assertIsNone(result)
  self.assertIn("differences",body);self.assertNotIn("paths",body)
 def test_zero_flow_is_trivially_valid(self):
  amounts=amap([])
  passed,_,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertTrue(passed)
  self.assertEqual(result["delivered"],0);self.assertEqual(result["paths"],[]);self.assertEqual(result["cycles"],[])
 def test_dangling_cycle_like_flow_fails_conservation(self):
  # 只在 C->T 有流，C 无来源：节点 C 失衡，验算失败且无分解。
  amounts=amap([("e8",4)])
  passed,body,result=fv.verify(NODES,ARCS,"S","T",[],amounts)
  self.assertFalse(passed);self.assertIsNone(result)
  self.assertTrue(any(v["node_id"]=="C" for v in body["differences"]["conservation_violations"]))

if __name__=="__main__":
 unittest.main(verbosity=2)
