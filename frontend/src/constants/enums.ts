export const ROLES:Record<string,string>={admin:'管理员',analyst:'联运分析员',viewer:'只读复核员'};
export const RUN_STATUS:Record<string,string>={queued:'排队中',running:'推演中',completed:'已完成',failed:'失败'};
export const PHASES:Record<string,string>={baseline:'基线网络',outage:'停用方案'};
export const DECISIONS:Record<string,string>={accepted:'接受并记录边界',needs_attention:'需要继续核查'};
export const CHECKS:Record<string,string>={flow_capacity_bounds:'逐边容量界',conservation:'逐节点流守恒',maxflow_equals_mincut:'最大流等于最小割',sink_not_residual_reachable:'残量源侧不含汇'};
export const SHEET_STATUS:Record<string,string>={open:'待封单',passed:'验算通过',failed:'验算失败'};
export const SHEET_CHECKS:Record<string,string>={capacity_bounds:'逐边容量界',node_conservation:'节点收发守恒',no_unknown_arcs:'无未知边',reconstruction_match:'逐边合计还原',paths_sum_equals_delivered:'路径合计=送达量',cycles_excluded_from_delivered:'循环不计送达',delivered_non_negative:'送达量非负'};
