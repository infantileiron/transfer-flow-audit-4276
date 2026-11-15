<script setup lang="ts">
import {ref,computed} from 'vue';
import type {Workspace} from '../stores/workspace';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import Status from '../components/common/Status.vue';
import Empty from '../components/common/Empty.vue';
import SheetDetail from '../components/SheetDetail.vue';
import {create} from '../api/flowSheets';
import {useAsync} from '../hooks/useAsync';
import {date} from '../utils/format';
const props=defineProps<{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}>();
const name=ref(''),runId=ref(''),expected=ref(1),selectedId=ref('');
const {busy,error,execute}=useAsync();
const scenarioName=(id:string)=>props.data.scenarios.find(s=>s.id===id)?.name||id;
const selected=computed(()=>props.data.flowSheets.find(f=>f.id===selectedId.value)||props.data.flowSheets[0]);
async function submit(){await execute(async()=>{await create({name:name.value,run_id:runId.value||props.data.runs.find(r=>r.status==='completed')?.id,expected_shards:Number(expected.value)});name.value='';await props.refresh()})}
async function pick(id:string){selectedId.value=id;await props.refresh()}
</script>
<template>
 <PageHeading code="07 / EXTERNAL FLOW VERIFICATION" title="外部逐边运量，先验算再分解。" description="绑定一次推演的停边快照，分片接收整数运量（缺边按零）；封单核对容量界与节点守恒，通过后分解为源汇路径与独立循环，循环不计送达。"/>
 <section class="paper" v-if="canWrite">
  <h2>新建配流验算单</h2>
  <form class="grid-form" @submit.prevent="submit">
   <label>验算单名称<input aria-label="验算单名称" required minlength="2" v-model="name" placeholder="如：外部调度·11月批次含循环"/></label>
   <label>绑定推演（取其停边与容量快照）<select aria-label="绑定推演" v-model="runId"><option v-for="r in data.runs" :key="r.id" :value="r.id">{{scenarioName(r.scenario_id)}} · {{r.status==='completed'?'可用':r.status}} · {{r.created_at.slice(0,10)}}</option></select></label>
   <label>预期分片数（0 表示不强制片数）<input type="number" min="0" max="1000" step="1" v-model.number="expected" aria-label="预期分片数"/></label>
   <Notice v-if="error" error>{{error}}</Notice>
   <button :disabled="busy">建单并绑定快照</button>
  </form>
 </section>
 <section class="paper">
  <h2>验算单台账</h2>
  <Empty v-if="!data.flowSheets.length">先在停用方案运行一次推演，再为外部逐边运量建立验算单。</Empty>
  <div class="table-scroll" v-else><table><thead><tr><th>名称</th><th>绑定推演</th><th>分片</th><th>状态</th><th>建单时间</th><th></th></tr></thead><tbody>
   <tr v-for="f in data.flowSheets" :key="f.id" :class="{active:selected?.id===f.id}">
    <td><b>{{f.name}}</b></td><td>{{scenarioName(data.runs.find(r=>r.id===f.run_id)?.scenario_id||'')}}</td><td>{{f.received_shards}}/{{f.expected_shards||'—'}}</td><td><Status :value="f.status"/></td><td>{{date(f.created_at)}}</td><td><button class="secondary" @click="pick(f.id)">回看明细</button></td>
   </tr>
  </tbody></table></div>
 </section>
 <SheetDetail v-if="selected" :key="selected.id" :sheet="selected" :can-write="canWrite" :refresh="refresh"/>
</template>
