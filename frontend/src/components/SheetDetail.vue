<script setup lang="ts">
import {ref,computed} from 'vue';
import type {FlowSheet} from '../types/domain';
import Notice from './common/Notice.vue';
import {SHEET_STATUS,SHEET_CHECKS} from '../constants/enums';
import {uploadShard,seal} from '../api/flowSheets';
import {useAsync} from '../hooks/useAsync';
import {date} from '../utils/format';
const props=defineProps<{sheet:FlowSheet;canWrite:boolean;refresh:()=>Promise<void>}>();
const shardIndex=ref(0);const shardText=ref('[{"arc_id":"e01","amount":3}]');
const hint=ref('');
const {busy,error,execute}=useAsync();
const open=computed(()=>props.sheet.status==='open');
const passed=computed(()=>props.sheet.status==='passed');
const diffs=computed(()=>(props.sheet.differences&&'differences' in props.sheet.differences?props.sheet.differences:null));
const result=computed(()=>(passed.value&&props.sheet.result&&'paths' in props.sheet.result?props.sheet.result:null));
async function submitShard(){
 hint.value='';
 await execute(async()=>{
  let entries:unknown;
  try{entries=JSON.parse(shardText.value)}catch{throw new Error('分片须为 JSON 数组，如 [{"arc_id":"e01","amount":3}]')}
  if(!Array.isArray(entries)||entries.some(e=>typeof e!=='object'||!e||typeof (e as {arc_id:unknown}).arc_id!=='string'))throw new Error('每条记录须含字符串 arc_id 与非负整数 amount');
  const r=await uploadShard(props.sheet.id,{shard_index:Number(shardIndex.value),entries});
  hint.value=r.deduplicated?'同号同文分片，已按重试幂等处理，未重复写入。':'分片已接收（编号 '+r.shard.shard_index+'）。';
  await props.refresh();
 });
}
async function doSeal(){await execute(async()=>{await seal(props.sheet.id);hint.value='';await props.refresh()})}
</script>
<template>
 <article class="sheet-detail">
  <div class="sheet-head">
   <div><span class="eyebrow">{{sheet.scenario_name}} · 绑定推演 {{sheet.run_id.slice(0,8)}}</span><h3>{{sheet.name}}</h3><p>分片 {{sheet.received_shards}}/{{sheet.expected_shards||'不限'}} · 建单 {{date(sheet.created_at)}}<template v-if="sheet.sealed_at"> · 封单 {{date(sheet.sealed_at)}}</template></p></div>
   <span :class="['status',sheet.status]">{{SHEET_STATUS[sheet.status]||sheet.status}}</span>
  </div>

  <section v-if="canWrite&&open" class="upload-box">
   <h4>分片补传（缺边按零；中断后可接着传）</h4>
   <div class="shard-form">
    <label class="shard-index">分片编号<input type="number" min="0" step="1" v-model.number="shardIndex" aria-label="分片编号"/></label>
    <label class="shard-payload">逐边整数运量 JSON<textarea rows="3" v-model="shardText" aria-label="分片运量JSON"></textarea></label>
   </div>
   <p class="caption">同号同文重试不重复写入；同号异文拒绝；每条边只能出现在一个分片；封单后拒绝任何改写。</p>
   <Notice v-if="error" error>{{error}}</Notice>
   <Notice v-if="hint">{{hint}}</Notice>
   <div class="shard-actions">
    <button :disabled="busy" @click="submitShard">接收本分片</button>
    <button class="secondary" :disabled="busy" @click="doSeal">封单并验算</button>
   </div>
  </section>

  <section class="paper-nest">
   <h4>已接收分片</h4>
   <div class="table-scroll"><table><thead><tr><th>编号</th><th>边条目数</th><th>内容校验码（前16位）</th><th>接收时间</th></tr></thead>
   <tbody><tr v-for="s in sheet.shards" :key="s.shard_index"><td><b>{{s.shard_index}}</b></td><td>{{s.entry_count}}</td><td class="mono">{{s.checksum.slice(0,16)}}</td><td>{{date(s.created_at)}}</td></tr>
   <tr v-if="!sheet.shards?.length"><td colspan="4" class="muted-cell">尚未接收分片，缺边将按零参与验算。</td></tr></tbody></table></div>
  </section>

  <Notice v-if="open" >验算单待封单：收齐分片后封单，系统按封单成功时的完整内容核对容量界与节点守恒，再决定是否发布分解。</Notice>

  <template v-if="diffs">
   <section class="paper-nest fail-nest">
    <h4>验算失败 · 差额清单（不发布分解结果）</h4>
    <p class="caption">送达量参考值：{{diffs.delivered}}</p>
    <div v-if="diffs.differences.unknown_arcs?.length" class="diff-block"><b>未知边</b><span class="tag warning" v-for="a in diffs.differences.unknown_arcs" :key="a">{{a}}</span></div>
    <div v-if="diffs.differences.capacity_violations?.length" class="diff-block"><b>容量超限</b>
     <div class="table-scroll"><table><thead><tr><th>边</th><th>运量</th><th>有效容量</th><th>超出</th></tr></thead><tbody>
      <tr v-for="v in diffs.differences.capacity_violations" :key="v.arc_id"><td>{{v.arc_id}}</td><td>{{v.amount}}</td><td>{{v.effective_capacity}}</td><td class="num-bad">+{{v.shortfall}}</td></tr>
     </tbody></table></div>
    </div>
    <div v-if="diffs.differences.conservation_violations?.length" class="diff-block"><b>节点收发失衡</b>
     <div class="table-scroll"><table><thead><tr><th>节点</th><th>实际余额</th><th>应然余额</th><th>差额</th></tr></thead><tbody>
      <tr v-for="v in diffs.differences.conservation_violations" :key="v.node_id"><td>{{v.node_id}}</td><td>{{v.balance}}</td><td>{{v.expected_balance}}</td><td :class="{'num-bad':v.delta!==0}">{{v.delta}}</td></tr>
     </tbody></table></div>
    </div>
    <div v-if="diffs.differences.reconstruction_differences?.length" class="diff-block"><b>分解无法还原原运量</b>
     <div class="table-scroll"><table><thead><tr><th>边</th><th>原运量</th><th>分解合计</th><th>差额</th></tr></thead><tbody>
      <tr v-for="v in diffs.differences.reconstruction_differences" :key="v.arc_id"><td>{{v.arc_id}}</td><td>{{v.amount}}</td><td>{{v.decomposed_amount}}</td><td>{{v.delta}}</td></tr>
     </tbody></table></div>
    </div>
   </section>
  </template>

  <template v-if="result">
   <div class="check-strip"><span v-for="(ok,k) in result.checks" :key="k" :class="{pass:ok}">{{SHEET_CHECKS[k]||k}} · {{ok?'通过':'失败'}}</span></div>
   <div class="sheet-metrics">
    <div><small>送达量（不计循环）</small><b>{{result.delivered}}</b></div>
    <div><small>源汇路径合计</small><b>{{result.path_flow_total}}</b></div>
    <div><small>独立循环合计</small><b>{{result.cycle_flow_total}}</b></div>
    <div><small>非零边 / 快照边</small><b>{{result.nonzero_arc_count}} / {{sheet.arc_count}}</b></div>
   </div>
   <section class="paper-nest">
    <h4>逐边对账（原运量 vs 分解合计）</h4>
    <div class="table-scroll"><table><thead><tr><th>边 / 方向</th><th>容量</th><th>原运量</th><th>分解合计</th><th>判定</th></tr></thead><tbody>
     <tr v-for="a in result.arc_reconciliation" :key="a.arc_id" :class="{disabled:a.disabled}"><td><b>{{a.arc_id}}</b><small>{{a.source}} → {{a.target}}</small></td><td>{{a.effective_capacity}}<small v-if="a.disabled">（停用）</small></td><td>{{a.amount}}</td><td>{{a.decomposed_amount}}</td><td><span class="tag" :class="{'pass':a.amount===a.decomposed_amount&&a.within_capacity,'warning':!a.within_capacity}">{{a.within_capacity?(a.amount===a.decomposed_amount?'一致':'不一致'):'超容量'}}</span></td></tr>
    </tbody></table></div>
   </section>
   <section class="paper-nest">
    <h4>节点收发守恒</h4>
    <div class="table-scroll"><table><thead><tr><th>节点</th><th>流入</th><th>流出</th><th>余额</th><th>应然</th></tr></thead><tbody>
     <tr v-for="c in result.conservation" :key="c.node_id"><td>{{c.node_id}}</td><td>{{c.inflow}}</td><td>{{c.outflow}}</td><td>{{c.balance}}</td><td>{{c.expected_balance}}</td></tr>
    </tbody></table></div>
   </section>
   <div class="two-col">
    <section class="paper-nest"><h4>源汇路径（{{result.paths.length}}条）</h4>
     <p v-for="p in result.paths" :key="'p'+p.index" class="flow-line"><b>{{p.amount}}</b><span>{{p.node_path.join(' → ')}}</span><small>{{p.arc_path.join('、')}}</small></p>
     <p v-if="!result.paths.length" class="caption">无源汇路径。</p>
    </section>
    <section class="paper-nest cycle-nest"><h4>独立循环（{{result.cycles.length}}条，不计送达）</h4>
     <p v-for="c in result.cycles" :key="'c'+c.index" class="flow-line"><b>{{c.amount}}</b><span>{{c.node_path.join(' → ')}}</span><small>{{c.arc_path.join('、')}}</small></p>
     <p v-if="!result.cycles.length" class="caption">本单不含循环。</p>
    </section>
   </div>
   <section class="paper-nest">
    <h4>平行边对账</h4>
    <p v-if="!result.parallel_groups.length" class="caption">无同端点平行边。</p>
    <div v-for="g in result.parallel_groups" :key="g.source+g.target" class="group-block"><b>{{g.source}} → {{g.target}}</b><span class="tag" v-for="a in g.arcs" :key="a.arc_id" :class="{'pass':a.amount===a.decomposed_amount}">{{a.arc_id}}：{{a.amount}} / 分解{{a.decomposed_amount}}</span></div>
    <h4 style="margin-top:18px">反向边对账</h4>
    <p v-if="!result.reverse_pairs.length" class="caption">无互为反向的边对。</p>
    <div v-for="(g,i) in result.reverse_pairs" :key="'r'+i" class="group-block"><b>{{g.forward_endpoints.join(' → ')}} / 反向</b>
     <span class="tag" v-for="a in [...g.forward,...g.backward]" :key="a.arc_id" :class="{'pass':a.amount===a.decomposed_amount}">{{a.arc_id}}：{{a.amount}} / 分解{{a.decomposed_amount}}</span>
    </div>
   </section>
  </template>
 </article>
</template>
