from sqlalchemy import String,Integer,JSON,ForeignKey,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class FlowShard(Base):
 __tablename__="flow_shards"
 __table_args__=(UniqueConstraint("sheet_id","shard_index"),)
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 sheet_id:Mapped[str]=mapped_column(ForeignKey("flow_sheets.id"))
 shard_index:Mapped[int]=mapped_column(Integer)
 checksum:Mapped[str]=mapped_column(String(64))
 entries:Mapped[list]=mapped_column(JSON)
 created_at:Mapped[str]=mapped_column(String(64))
