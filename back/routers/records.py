# backend/routers/records.py
from fastapi import APIRouter, HTTPException, Query
from db import SessionLocal
from models import DetectRecord
from sqlalchemy import desc
from fastapi.responses import FileResponse
import os
import json
from config import RESULT_DIR, UPLOAD_DIR, CAMERA_DIR
import re
from typing import Optional

router = APIRouter()


def _make_safe_url(filepath: Optional[str], base_dir: str, prefix: str) -> Optional[str]:
    """生成安全的文件访问 URL，防止路径遍历"""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        real_path = os.path.realpath(filepath)
        real_base = os.path.realpath(base_dir)
        if not real_path.startswith(real_base):
            return None
        filename = os.path.basename(filepath)
        if re.match(r"^[^\x00/\x00]+$", filename):  # 禁止 / 和空字符即可
            return f"{prefix}/{filename}"
    except Exception:
        return None
    return None


@router.get("/records/list")
def list_records(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    type: str = None
):
    """获取检测记录列表"""
    db = SessionLocal()
    try:
        query = db.query(DetectRecord)
        if type:
            query = query.filter(DetectRecord.type == type)

        total = query.count()
        offset = (page - 1) * limit

        records = (
            query
            .order_by(desc(DetectRecord.detect_time))
            .offset(offset)
            .limit(limit)
            .all()
        )

        data = []
        for r in records:
            detection_count = 0
            if r.objects:
                try:
                    obj = json.loads(r.objects)
                    detection_count = len(obj) if isinstance(obj, list) else 0
                except:
                    pass

            record_info = {
                "id": r.id,
                "type": r.type,
                "filename": r.filename,
                "detect_time": r.detect_time.isoformat() if r.detect_time else None,
                "detection_count": detection_count,
                "has_result": bool(r.result_path and os.path.exists(r.result_path))
            }
            data.append(record_info)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
    finally:
        db.close()


@router.get("/records/{record_id}")
def get_record_detail(record_id: int):
    """获取单条记录详情（含 source_url 和 result_url）"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        objects_data = []
        if record.objects:
            try:
                objects_data = json.loads(record.objects)
            except:
                objects_data = []

        source_url = _make_safe_url(record.source_path, UPLOAD_DIR, "/files/upload")
        result_url = _make_safe_url(record.result_path, RESULT_DIR, "/files/result")

        return {
            "id": record.id,
            "type": record.type,
            "filename": record.filename,
            "detect_time": record.detect_time.isoformat() if record.detect_time else None,
            "source_url": source_url,
            "result_url": result_url,  # ← 现在是 /files/result/xxx
            "objects": objects_data,
            "file_status": {
                "source_exists": source_url is not None,
                "result_exists": result_url is not None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
    finally:
        db.close()


@router.get("/records/file/{record_id}")
def get_record_file(
    record_id: int,
    which: str = "result",
    check_exists: bool = True
):
    """获取记录对应的原始或结果文件（兼容旧接口）"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        file_path = record.result_path if which == "result" else record.source_path
        if which not in ["result", "source"] or not file_path:
            raise HTTPException(status_code=400, detail="无效的 which 参数或文件路径")

        allowed_dirs = [d for d in [RESULT_DIR, UPLOAD_DIR, CAMERA_DIR] if d]
        real_file = os.path.realpath(file_path)
        if not any(real_file.startswith(os.path.realpath(d)) for d in allowed_dirs):
            raise HTTPException(status_code=403, detail="文件访问被拒绝")

        if check_exists and not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        return FileResponse(file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件访问失败: {str(e)}")
    finally:
        db.close()


@router.delete("/records/{record_id}")
def delete_record(record_id: int, delete_files: bool = False):
    """删除记录（可选删除物理文件）"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        file_paths = []
        if record.source_path:
            file_paths.append(record.source_path)
        if record.result_path and record.result_path != record.source_path:
            file_paths.append(record.result_path)

        db.delete(record)
        db.commit()

        deleted_files = []
        if delete_files:
            for fp in file_paths:
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                        deleted_files.append(fp)
                    except OSError:
                        pass  # 忽略删除失败

        return {
            "message": "记录删除成功",
            "record_id": record_id,
            "deleted_files": deleted_files if delete_files else []
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        db.close()