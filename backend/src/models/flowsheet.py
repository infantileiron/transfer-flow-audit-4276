from sqlalchemy import String,Integer,JSON,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class FlowSheet(Base):
 __tablename__="flow_sheets"
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 name:Mapped[str]=mapped_column(String(160),unique=True)
 run_id:Mapped[str]=mapped_column(ForeignKey("network_runs.id"))
 expected_shards:Mapped[int]=mapped_column(Integer,default=0)
 received_shards:Mapped[int]=mapped_column(Integer,default=0)
 status:Mapped[str]=mapped_column(String(30),default="open")
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 differences:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default="")
 created_at:Mapped[str]=mapped_column(String(64))
 sealed_at:Mapped[str]=mapped_column(String(64),default="")
