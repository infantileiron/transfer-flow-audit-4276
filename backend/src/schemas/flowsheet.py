from pydantic import BaseModel,Field,field_validator
class SheetInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 run_id:str
 expected_shards:int=Field(default=0,ge=0,le=1000)
class ShardEntry(BaseModel):
 arc_id:str=Field(min_length=1,max_length=60)
 amount:int=Field(ge=0,le=10_000_000)
 @field_validator("amount",mode="before")
 @classmethod
 def not_bool(cls,v):
  if isinstance(v,bool):raise ValueError("运量须为整数，不能是布尔值")
  return v
class ShardInput(BaseModel):
 shard_index:int=Field(ge=0,le=999)
 entries:list[ShardEntry]=Field(max_length=200)
 @field_validator("entries")
 @classmethod
 def unique_arc(cls,v):
  ids=[e.arc_id for e in v]
  if len(ids)!=len(set(ids)):raise ValueError("同一分片内边ID不能重复")
  return v
