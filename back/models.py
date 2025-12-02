from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import JSON
from datetime import datetime

Base = declarative_base()

class DetectRecord(Base):
    __tablename__ = "detect_record"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20))
    filename = Column(String(255))
    source_path = Column(String(512))
    result_path = Column(String(512))
    result_url = Column(String(512))
    objects = Column(JSON)
    detect_time = Column(DateTime, default=datetime.utcnow)