# backend/routers/records.py
from fastapi import APIRouter, HTTPException, Query
from db import SessionLocal
from models import DetectRecord
from sqlalchemy import desc
from fastapi.responses import FileResponse
import os
import json
import logging
from config import RESULT_DIR, UPLOAD_DIR, CAMERA_DIR, TRANSCODED_DIR
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)  # 添加logger定义


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

        # 修复：正确获取记录
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
            detection_count = 0
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

            # 检查结果文件是否存在（包括转码目录）
            result_exists = False
            if r.result_path:
                # 检查原始结果文件
                result_exists = os.path.exists(r.result_path)
                if not result_exists:
                    # 检查转码目录
                    filename = os.path.basename(r.result_path)
                    transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{filename}")
                    result_exists = os.path.exists(transcoded_path)

            record_info = {
                "id": r.id,
                "type": r.type,
                "filename": r.filename,
                "detect_time": r.detect_time.isoformat() if r.detect_time else None,
                "detection_count": detection_count,
                "has_result": result_exists
            }
            data.append(record_info)

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "data": data
        }
    except Exception as e:
        logger.error(f"❌ 查询记录列表失败: {str(e)}")  # 现在logger已定义
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

        # 添加详细的调试信息
        logger.info(f"🔍 查询记录ID: {record_id}")
        logger.info(f"📁 源文件路径: {record.source_path}")
        logger.info(f"📁 结果文件路径: {record.result_path}")
        logger.info(f"📊 记录类型: {record.type}")

        # 检查文件存在性
        source_exists = False
        result_exists = False

        if record.source_path:
            source_abs_path = os.path.abspath(record.source_path)
            source_exists = os.path.exists(source_abs_path)
            logger.info(f"🔍 源文件存在: {source_exists} - {source_abs_path}")

        if record.result_path:
            result_abs_path = os.path.abspath(record.result_path)
            result_exists = os.path.exists(result_abs_path)
            logger.info(f"🔍 结果文件存在: {result_exists} - {result_abs_path}")

            # 检查转码文件
            if not result_exists:
                filename = os.path.basename(record.result_path)
                transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{filename}")
                transcoded_exists = os.path.exists(transcoded_path)
                logger.info(f"🔍 转码文件存在: {transcoded_exists} - {transcoded_path}")
                if transcoded_exists:
                    result_exists = True

        # 解析检测结果
        objects_data = []
        if record.objects:
            try:
                objects_data = json.loads(record.objects)
                logger.info(f"📊 检测对象数量: {len(objects_data)}")
            except Exception as e:
                logger.error(f"❌ 解析对象数据失败: {e}")
                objects_data = []

        return {
            "id": record.id,
            "type": record.type,
            "filename": record.filename,
            "detect_time": r.detect_time.isoformat() if r.detect_time else None,
            "source_path": record.source_path,
            "result_path": record.result_path,
            "objects": objects_data,
            "file_status": {
                "source_exists": source_exists,
                "result_exists": result_exists
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询记录详情失败: {str(e)}")
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

        # 修复：更健壮的文件路径检查
        allowed_dirs = [RESULT_DIR, UPLOAD_DIR, CAMERA_DIR, TRANSCODED_DIR]

        # 确保所有目录路径都是绝对路径
        allowed_dirs = [os.path.abspath(str(dir_path)) for dir_path in allowed_dirs if dir_path]

        # 规范化文件路径
        if file_path and os.path.isabs(file_path):
            file_abs_path = file_path
        else:
            file_abs_path = os.path.abspath(file_path)

        # 检查文件路径是否在允许的目录内
        allowed = False
        for allowed_dir in allowed_dirs:
            if allowed_dir and file_abs_path.startswith(allowed_dir):
                allowed = True
                break

        if not allowed:
            logger.error(f"❌ 文件访问被拒绝: {file_abs_path}")
            logger.error(f"❌ 允许的目录: {allowed_dirs}")
            raise HTTPException(status_code=403, detail="文件访问被拒绝")

        # 如果是结果文件，先检查原始路径，如果不存在则检查转码目录
        actual_file_path = file_abs_path
        if which == "result" and check_exists and not os.path.exists(actual_file_path):
            # 检查转码目录
            filename = os.path.basename(file_abs_path)
            transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{filename}")
            if os.path.exists(transcoded_path):
                actual_file_path = transcoded_path
                logger.info(f"🔍 使用转码文件: {actual_file_path}")
            else:
                raise HTTPException(status_code=404, detail="文件不存在")
        elif check_exists and not os.path.exists(actual_file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        logger.info(f"✅ 返回文件: {actual_file_path}")
        return FileResponse(actual_file_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 文件访问失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件访问失败: {str(e)}")
    finally:
        db.close()


@router.get("/records/debug/{record_id}")
def debug_record(record_id: int):
    """调试记录文件路径"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            return {"error": "记录不存在"}

        # 检查所有可能的文件路径
        paths_to_check = []

        if record.source_path:
            paths_to_check.append(("源文件", record.source_path))

        if record.result_path:
            paths_to_check.append(("结果文件", record.result_path))

            # 检查转码文件
            filename = os.path.basename(record.result_path)
            transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{filename}")
            paths_to_check.append(("转码文件", transcoded_path))

        # 检查每个路径
        path_status = []
        for name, path in paths_to_check:
            abs_path = os.path.abspath(path) if path else None
            exists = os.path.exists(abs_path) if abs_path else False
            path_status.append({
                "name": name,
                "path": path,
                "absolute_path": abs_path,
                "exists": exists
            })

        # 检查允许的目录
        allowed_dirs = [RESULT_DIR, UPLOAD_DIR, CAMERA_DIR, TRANSCODED_DIR]
        allowed_dirs_info = []
        for dir_path in allowed_dirs:
            abs_dir = os.path.abspath(str(dir_path)) if dir_path else None
            exists = os.path.exists(abs_dir) if abs_dir else False
            allowed_dirs_info.append({
                "path": dir_path,
                "absolute_path": abs_dir,
                "exists": exists
            })

        return {
            "record_id": record_id,
            "type": record.type,
            "filename": record.filename,
            "path_status": path_status,
            "allowed_dirs": allowed_dirs_info
        }
    except Exception as e:
        return {"error": str(e)}
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
            file_paths.append(record.source_path)
        if record.result_path and record.result_path != record.source_path:
            file_paths.append(record.result_path)

        # 删除数据库记录
        db.delete(record)
        db.commit()

        # 可选删除文件
        if delete_files:
            deleted_files = []
            for file_path in file_paths:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                    except Exception as e:
                        # 文件删除失败不影响主要操作
                        logger.warning(f"删除文件失败 {file_path}: {e}")

                # 如果是结果文件，同时删除转码文件
                if file_path == record.result_path:
                    filename = os.path.basename(file_path)
                    transcoded_path = os.path.join(TRANSCODED_DIR, filename)
                    if os.path.exists(transcoded_path):
                        try:
                            os.remove(transcoded_path)
                            deleted_files.append(transcoded_path)
                        except Exception as e:
                            logger.warning(f"删除转码文件失败 {transcoded_path}: {e}")

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