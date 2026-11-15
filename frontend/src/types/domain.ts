export interface User{email:string;role:string}
export interface Node{node_id:string;label:string;x:number;y:number}
export interface ArcShape{arc_id:string;source:string;target:string;capacity:number;travel_minutes:number}
export interface Arc extends ArcShape{id:string;dataset_id:string;created_at:string}
export interface Dataset{id:string;name:string;source:string;nodes:Node[];created_at:string}
export interface Scenario{id:string;name:string;dataset_id:string;source_node:string;sink_node:string;disabled_arc_ids:string[];arc_snapshot:ArcShape[];created_at:string}
export interface ArcFlow extends ArcShape{effective_capacity:number;flow:number;residual_forward:number;residual_reverse:number;disabled:boolean}
export interface Conservation{node_id:string;inflow:number;outflow:number;balance:number;expected_balance:number;conserved:boolean}
export interface MaxFlow{value:number;cut_capacity:number;source_side:string[];sink_side:string[];cut_arcs:ArcFlow[];arc_flows:ArcFlow[];conservation:Conservation[];checks:Record<string,boolean>;augmentations:{amount:number;steps:{arc_id:string;direction:number;source:string;target:string}[]}[];residual_edge_count:number}
export interface Shortest{reachable:boolean;minutes:number|null;node_path:string[];arc_path:string[]}
export interface Phase{max_flow:MaxFlow;shortest:Shortest}
export interface Result{nodes:Node[];arcs:ArcShape[];source:string;sink:string;disabled_arc_ids:string[];baseline:Phase;outage:Phase;impact:{flow_reduction:number;shortest_time_change_minutes:number|null;lost_reachability:boolean};checksum:string;assumptions:string[]}
export interface Run{id:string;scenario_id:string;status:string;result:Result;error:string;created_at:string}
export interface Review{id:string;run_id:string;note:string;decision:string;author:string;created_at:string}
export interface Report{id:string;run_id:string;title:string;published_by:string;created_at:string}
export interface Audit{id:string;actor:string;action:string;status:number;created_at:string}
export interface ShardSummary{shard_index:number;checksum:string;entry_count:number;created_at:string}
export interface ArcReconciliation{arc_id:string;source:string;target:string;capacity:number;effective_capacity:number;disabled:boolean;amount:number;decomposed_amount:number;within_capacity:boolean}
export interface FlowPath{index:number;amount:number;node_path:string[];arc_path:string[]}
export interface GroupedArc{arc_id:string;amount:number;decomposed_amount:number}
export interface SheetResult{source:string;sink:string;disabled_arc_ids:string[];delivered:number;path_flow_total:number;cycle_flow_total:number;nonzero_arc_count:number;arc_reconciliation:ArcReconciliation[];conservation:Conservation[];paths:FlowPath[];cycles:FlowPath[];parallel_groups:{source:string;target:string;arcs:GroupedArc[]}[];reverse_pairs:{forward_endpoints:string[];forward:GroupedArc[];backward:GroupedArc[]}[];checks:Record<string,boolean>}
export interface SheetDifferences{differences:{unknown_arcs?:string[];capacity_violations?:{arc_id:string;amount:number;effective_capacity:number;shortfall:number}[];conservation_violations?:{node_id:string;balance:number;expected_balance:number;delta:number}[];reconstruction_differences?:{arc_id:string;amount:number;decomposed_amount:number;delta:number}[]};delivered:number;conservation:Conservation[]}
export interface FlowSheet{id:string;name:string;run_id:string;expected_shards:number;received_shards:number;status:string;result:SheetResult|Record<string,never>;differences:SheetDifferences|Record<string,never>;error:string;created_at:string;sealed_at:string;shards?:ShardSummary[];arc_count?:number;scenario_name?:string}
