"""配流验算纯函数：分片校验和、容量/守恒核对、源汇路径与独立循环分解。

只依赖标准库，入参均为普通 dict/list，便于在不启动 Web/数据库的情况下验证。
平行边与反向边始终以各自 arc_id 独立参与，不按端点合并。
"""
import hashlib,json
from collections import deque,defaultdict

def shard_checksum(entries):
 """对分片内容做规范化 SHA256；同内容不同条目顺序视为同文。"""
 canonical=json.dumps(sorted((e["arc_id"],int(e["amount"])) for e in entries),ensure_ascii=False,separators=(",",":"))
 return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def aggregate(arc_ids,shard_entries):
 """把各分片条目合计为逐边运量；同一 arc_id 跨片重复由上传环节拦截，这里再兜底求和。"""
 totals={aid:0 for aid in arc_ids}
 for entries in shard_entries:
  for e in entries:totals[e["arc_id"]]=totals.get(e["arc_id"],0)+int(e["amount"])
 return totals

def reconcile(node_ids,arcs,source,sink,disabled,amounts):
 """容量界与节点收发守恒核对，返回 (通过标志, 差额清单, 守恒行, 送达量)。"""
 meta={a["arc_id"]:a for a in arcs};blocked=set(disabled)
 unknown=sorted(aid for aid in amounts if aid not in meta)
 capacity_violations=[]
 for aid in sorted(meta):
  effective=0 if aid in blocked else meta[aid]["capacity"]
  amount=amounts.get(aid,0)
  if amount<0 or amount>effective:
   capacity_violations.append({"arc_id":aid,"amount":amount,"effective_capacity":effective,"shortfall":amount-effective})
 inflow=defaultdict(int);outflow=defaultdict(int)
 for aid,a in meta.items():
  amount=amounts.get(aid,0)
  outflow[a["source"]]+=amount;inflow[a["target"]]+=amount
 delivered=outflow[source]-inflow[source]
 conservation=[];conservation_violations=[]
 for n in node_ids:
  balance=outflow[n]-inflow[n]
  expected=delivered if n==source else -delivered if n==sink else 0
  row={"node_id":n,"inflow":inflow[n],"outflow":outflow[n],"balance":balance,"expected_balance":expected,"conserved":balance==expected}
  conservation.append(row)
  if not row["conserved"]:conservation_violations.append({"node_id":n,"balance":balance,"expected_balance":expected,"delta":balance-expected})
 differences={}
 if unknown:differences["unknown_arcs"]=unknown
 if capacity_violations:differences["capacity_violations"]=capacity_violations
 if conservation_violations:differences["conservation_violations"]=conservation_violations
 if delivered<0 and not any(v["node_id"]==source for v in conservation_violations):differences["negative_delivered"]=delivered
 passed=not differences and delivered>=0
 return passed,differences,conservation,delivered

def _sink_path(adj,target_of,remaining,source,sink):
 parent={source:(None,None)};queue=deque([source])
 while queue:
  u=queue.popleft()
  if u==sink:break
  for aid in sorted(adj[u]):
   if remaining.get(aid,0)>0:
    v=target_of[aid]
    if v not in parent:parent[v]=(u,aid);queue.append(v)
 if sink not in parent:return None
 arc_path=[];node=sink
 while node!=source:
  u,aid=parent[node];arc_path.append(aid);node=u
 arc_path.reverse();node_path=[source]
 for aid in arc_path:node_path.append(target_of[aid])
 return node_path,arc_path

def _find_cycle(node_ids,adj,remaining,target_of):
 """三色 DFS 找正流量闭环；命中灰节点即沿父链还原循环。"""
 color={n:0 for n in node_ids};parent_node={};parent_arc={}
 for root in sorted(node_ids):
  if color[root]!=0:continue
  color[root]=1;stack=[(root,iter(sorted(adj[root])))]
  while stack:
   u,it=stack[-1];advanced=False
   for aid in it:
    if remaining.get(aid,0)<=0:continue
    v=target_of[aid]
    if color[v]==0:
     color[v]=1;parent_node[v]=u;parent_arc[v]=aid
     stack.append((v,iter(sorted(adj[v]))));advanced=True;break
    if color[v]==1:
     cyc_nodes=[];cyc_arcs=[];x=u
     while x!=v:
      cyc_nodes.append(x);cyc_arcs.append(parent_arc[x]);x=parent_node[x]
     cyc_nodes.append(v);cyc_nodes.reverse();cyc_nodes.append(v)
     cyc_arcs.reverse();cyc_arcs.append(aid)
     return cyc_nodes,cyc_arcs
   if not advanced:color[u]=2;stack.pop()
 return None

def decompose(node_ids,arcs,source,sink,amounts):
 """把整数逐边运量分解为源汇路径与独立循环，返回路径、循环与逐边分解合计。"""
 target_of={a["arc_id"]:a["target"] for a in arcs}
 adj={n:[] for n in node_ids}
 for a in arcs:adj[a["source"]].append(a["arc_id"])
 remaining={aid:int(amounts.get(aid,0)) for aid in target_of}
 paths=[];cycles=[]
 while True:
  found=_sink_path(adj,target_of,remaining,source,sink)
  if found:
   node_path,arc_path=found;amount=min(remaining[a] for a in arc_path)
   for aid in arc_path:remaining[aid]-=amount
   paths.append({"index":len(paths)+1,"amount":amount,"node_path":node_path,"arc_path":arc_path})
   continue
  cycle=_find_cycle(node_ids,adj,remaining,target_of)
  if not cycle:break
  cyc_nodes,cyc_arcs=cycle;amount=min(remaining[a] for a in cyc_arcs)
  for aid in cyc_arcs:remaining[aid]-=amount
  cycles.append({"index":len(cycles)+1,"amount":amount,"node_path":cyc_nodes,"arc_path":cyc_arcs})
 decomposed=defaultdict(int)
 for p in paths:
  for aid in p["arc_path"]:decomposed[aid]+=p["amount"]
 for c in cycles:
  for aid in c["arc_path"]:decomposed[aid]+=c["amount"]
 return paths,cycles,dict(decomposed),remaining

def edge_groupings(arcs,amounts,decomposed):
 """平行边（同端点多条）与反向边（u→v 与 v→u 并存）分别对账。"""
 pairs=defaultdict(list)
 for a in arcs:pairs[(a["source"],a["target"])].append(a["arc_id"])
 def cell(aid):return {"arc_id":aid,"amount":amounts.get(aid,0),"decomposed_amount":decomposed.get(aid,0)}
 parallel=[]
 for (u,v),ids in sorted(pairs.items()):
  if len(ids)>1:parallel.append({"source":u,"target":v,"arcs":[cell(aid) for aid in sorted(ids)]})
 reverse=[];seen=set()
 for (u,v),ids in sorted(pairs.items()):
  if (v,u) in pairs and (u,v) not in seen and (v,u) not in seen:
   seen.add((u,v));seen.add((v,u))
   reverse.append({"forward_endpoints":[u,v],"forward":[cell(aid) for aid in sorted(ids)],"backward":[cell(aid) for aid in sorted(pairs[(v,u)])]})
 return parallel,reverse

def verify(node_ids,arcs,source,sink,disabled,amounts):
 """封单验算主流程：先核对，通过才分解；失败只回差额，不发布分解。"""
 passed,differences,conservation,delivered=reconcile(node_ids,arcs,source,sink,disabled,amounts)
 if not passed:
  return False,{"differences":differences,"delivered":delivered,"conservation":conservation},None
 paths,cycles,decomposed,leftover=decompose(node_ids,arcs,source,sink,amounts)
 reconstruction=[]
 for aid in sorted({**amounts,**decomposed}):
  want=amounts.get(aid,0);got=decomposed.get(aid,0)
  if want!=got:reconstruction.append({"arc_id":aid,"amount":want,"decomposed_amount":got,"delta":got-want})
 if any(v>0 for v in leftover.values()):
  for aid,v in leftover.items():
   if v>0 and not any(r["arc_id"]==aid for r in reconstruction):reconstruction.append({"arc_id":aid,"amount":amounts.get(aid,0),"decomposed_amount":decomposed.get(aid,0),"delta":decomposed.get(aid,0)-amounts.get(aid,0)})
 path_total=sum(p["amount"] for p in paths);cycle_total=sum(c["amount"] for c in cycles)
 parallel,reverse=edge_groupings(arcs,amounts,decomposed)
 checks={"capacity_bounds":True,"node_conservation":True,"no_unknown_arcs":True,"reconstruction_match":not reconstruction,"paths_sum_equals_delivered":path_total==delivered,"cycles_excluded_from_delivered":True,"delivered_non_negative":delivered>=0}
 if reconstruction:
  return False,{"differences":{"reconstruction_differences":reconstruction},"delivered":delivered,"conservation":conservation},None
 meta={a["arc_id"]:a for a in arcs};blocked=set(disabled)
 arc_rows=[]
 for a in sorted(arcs,key=lambda x:x["arc_id"]):
  aid=a["arc_id"];effective=0 if aid in blocked else a["capacity"]
  arc_rows.append({"arc_id":aid,"source":a["source"],"target":a["target"],"capacity":a["capacity"],"effective_capacity":effective,"disabled":aid in blocked,"amount":amounts.get(aid,0),"decomposed_amount":decomposed.get(aid,0),"within_capacity":0<=amounts.get(aid,0)<=effective})
 result={"source":source,"sink":sink,"disabled_arc_ids":sorted(blocked),"delivered":delivered,"path_flow_total":path_total,"cycle_flow_total":cycle_total,"nonzero_arc_count":sum(1 for v in amounts.values() if v>0),"arc_reconciliation":arc_rows,"conservation":conservation,"paths":paths,"cycles":cycles,"parallel_groups":parallel,"reverse_pairs":reverse,"checks":checks}
 return True,{},result
