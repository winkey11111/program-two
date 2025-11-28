# backend/routers/records.py
from fastapi import APIRouter, HTTPException, Query
from db import SessionLocal
from models import DetectRecord
from sqlalchemy import desc
from fastapi.responses import FileResponse
import os
import json
from config import RESULT_DIR, UPLOAD_DIR, CAMERA_DIR
from typing import Optional

router = APIRouter()


@router.get("/records/list")
def list_records(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        type: str = None
):
    """获取检测记录列表"""
    db = SessionLocal()  # 修复：应该是 SessionLocal()
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
            # 解析检测结果统计信息
            objects_data = []
            if r.objects:
                try:
                    objects_data = json.loads(r.objects)
                    if isinstance(objects_data, list):
                        # 统计检测目标数量
                        detection_count = len(objects_data)
                    else:
                        detection_count = 0
                except:
                    detection_count = 0
            else:
                detection_count = 0

            record_info = {
                "id": r.id,
                "type": r.type,
                "filename": r.filename,
                "detect_time": r.detect_time.isoformat() if r.detect_time else None,  # 修复：添加了缺失的括号和引号
                "detection_count": detection_count,
                "has_result": os.path.exists(r.result_path) if r.result_path else False
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
    """获取单条记录的详细信息"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        # 解析检测结果
        objects_data = []
        if record.objects:
            try:
                objects_data = json.loads(record.objects)
            except:
                objects_data = []

        # 检查文件是否存在
        source_exists = os.path.exists(record.source_path) if record.source_path else False
        result_exists = os.path.exists(record.result_path) if record.result_path else False

        return {
            "id": record.id,
            "type": record.type,
            "filename": record.filename,
            "detect_time": record.detect_time.isoformat() if record.detect_time else None,
            "source_path": record.source_path,
            "result_path": record.result_path,
            "objects": objects_data,
            "file_status": {  # 修复：添加了缺失的引号
                "source_exists": source_exists,
                "result_exists": result_exists
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
    """获取记录对应的文件"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        if which == "result":
            file_path = record.result_path
        elif which == "source":
            file_path = record.source_path
        else:
            raise HTTPException(status_code=400, detail="which参数必须是'result'或'source'")

        if not file_path:
            raise HTTPException(status_code=404, detail="文件路径不存在")

        # 确保文件路径在允许的目录内
        allowed_dirs = [RESULT_DIR, UPLOAD_DIR, CAMERA_DIR]
        if not any(file_path.startswith(str(dir_path)) for dir_path in allowed_dirs if dir_path):
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
    """删除记录（可选删除文件）"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        # 记录文件路径用于后续删除
        file_paths = []
        if record.source_path:
            file_paths.append(record.source_path)  # 修复：添加了缺失的括号
        if record.result_path and record.result_path != record.source_path:
            file_paths.append(record.result_path)

        # 删除数据库记录
        db.delete(record)
        db.commit()

        # 可选删除文件
        if delete_files:
            deleted_files = []
            for file_path in file_paths:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                    except Exception as e:
                        # 文件删除失败不影响主要操作
                        pass

            return {
                "message": "记录删除成功",
                "deleted_files": deleted_files,
                "record_id": record_id
            }
        else:
            return {
                "message": "记录删除成功（文件保留）",
                "record_id": record_id
            }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        db.close()