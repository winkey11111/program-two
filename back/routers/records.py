# backend/routers/records.py
from fastapi import APIRouter, HTTPException, Query
from db import SessionLocal
from models import DetectRecord
from sqlalchemy import desc
from fastapi.responses import FileResponse
import os
from config import RESULT_DIR, UPLOAD_DIR, CAMERA_DIR

router = APIRouter()

@router.get("/records/list")
def list_records(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    type: str = None
):
    db = SessionLocal()
    try:
        # 构建查询
        query = db.query(DetectRecord)
        if type:
            query = query.filter(DetectRecord.type == type)

        # 获取总数（用于分页）
        total = query.count()

        # 分页查询：按时间倒序，跳过 (page-1)*limit 条
        offset = (page - 1) * limit
        records = (
            query
            .order_by(desc(DetectRecord.detect_time))
            .offset(offset)
            .limit(limit)
            .all()
        )

        # 转换为字典列表
        data = [
            {
                "id": r.id,
                "type": r.type,
                "filename": r.filename,
                "detect_time": r.detect_time.isoformat() if r.detect_time else None,
            }
            for r in records
        ]

        return {
            "total": total,
            "data": data
        }

    finally:
        db.close()


@router.get("/records/file/{id}")
def get_record_file(id: int, which: str = "result"):
    db = SessionLocal()
    try:
        r = db.query(DetectRecord).filter(DetectRecord.id == id).first()
        if not r:
            raise HTTPException(status_code=404, detail="record not found")
        
        path = r.result_path if which == "result" else r.source_path
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="file not found")
        
        return FileResponse(path)
    finally:
        db.close()