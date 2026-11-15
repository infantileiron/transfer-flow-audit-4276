<script setup lang="ts">import {RUN_STATUS,SHEET_STATUS} from '../../constants/enums';defineProps<{value:string}>();
const label=(v:string)=>RUN_STATUS[v]||SHEET_STATUS[v]||v;
</script><template><span :class="['status',value]">{{label(value)}}</span></template>
