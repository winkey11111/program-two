# backend/routers/records.py
from fastapi import APIRouter, HTTPException
from db import SessionLocal
from models import DetectRecord
from sqlalchemy import desc
from fastapi.responses import FileResponse
import os
from config import RESULT_DIR, UPLOAD_DIR, CAMERA_DIR

router = APIRouter()

@router.get("/records/list")
def list_records(limit: int = 50, type: str = None):
    db = SessionLocal()
    q = db.query(DetectRecord)
    if type:
        q = q.filter(DetectRecord.type == type)
    rows = q.order_by(desc(DetectRecord.detect_time)).limit(limit).all()
    db.close()
    return [{"id": r.id, "type": r.type, "filename": r.filename, "source_path": r.source_path, "result_path": r.result_path, "objects": r.objects, "detect_time": r.detect_time} for r in rows]

@router.get("/records/file/{id}")
def get_record_file(id: int, which: str = "result"):
    db = SessionLocal()
    r = db.query(DetectRecord).filter(DetectRecord.id == id).first()
    db.close()
    if not r:
        raise HTTPException(status_code=404, detail="record not found")
    path = r.result_path if which == "result" else r.source_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)
