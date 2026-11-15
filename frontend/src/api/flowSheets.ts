import {request,post} from './client';
import type {FlowSheet} from '../types/domain';
export const list=()=>request<FlowSheet[]>('/flow-sheets');
export const create=(data:unknown)=>post<FlowSheet>('/flow-sheets',data);
export const detail=(id:string)=>request<FlowSheet>('/flow-sheets/'+id);
export const uploadShard=(id:string,data:unknown)=>post<{deduplicated:boolean;shard:{shard_index:number}}>('/flow-sheets/'+id+'/shards',data);
export const seal=(id:string)=>post<FlowSheet>('/flow-sheets/'+id+'/seal',{});
