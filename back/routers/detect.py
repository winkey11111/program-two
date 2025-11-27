# backend/routers/detect.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import time
import shutil
import aiofiles
import json
from typing import List, Dict, Any, Optional
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord, Base
from ultralytics import YOLO
import cv2
import numpy as np
import base64
from io import BytesIO

router = APIRouter()
model = YOLO(MODEL_PATH)


# 确保数据库表存在
def init_db():
    from db import engine
    Base.metadata.create_all(bind=engine)


init_db()


@router.post("/detect/image")
async def detect_image(file: UploadFile = File(...), conf: float = 0.25):
    """
    增强的图像检测接口 - 支持框编号和自定义显示
    """
    # 文件类型检查
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".bmp"]:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    # 生成唯一文件名
    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    # 保存上传的文件
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # 运行推理
    results = model.predict(source=save_path, imgsz=1280, conf=conf, save=False, verbose=False)
    r = results[0]

    # 读取原始图片
    img = cv2.imread(save_path)
    if img is None:
        raise HTTPException(status_code=500, detail="无法读取图片文件")

    detections = []
    detection_id = 1  # 从1开始的检测框ID

    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls_ids = r.boxes.cls.cpu().numpy().astype(int)

        for i, (box, confs_i, cls_i) in enumerate(zip(boxes, confs, cls_ids)):
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls_i)]

            # 为每个检测框分配唯一ID和颜色
            color = get_color_by_class_and_id(label, detection_id)

            # 检测框信息
            detection_info = {
                "id": detection_id,  # 唯一标识符
                "class": label,
                "confidence": float(confs_i),
                "bbox": [x1, y1, x2, y2],
                "color": color,  # 颜色信息供前端使用
                "visible": True,  # 默认可见
                "area": (x2 - x1) * (y2 - y1)  # 框的面积
            }
            detections.append(detection_info)

            # 绘制检测框（带编号）
            draw_detection_box(img, detection_info)

            detection_id += 1

    # 生成带编号的结果图片
    out_name = f"res_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    # 保存到数据库
    db = SessionLocal()
    try:
        record = DetectRecord(
            type="image",
            filename=save_name,
            source_path=save_path,
            result_path=out_path,
            objects=json.dumps(detections)  # 保存为JSON字符串
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # 返回增强的响应
        return {
            "id": record.id,
            "result_url": f"/api/files/result/{out_name}",
            "detections": detections,  # 包含完整检测信息
            "summary": {
                "total_detections": len(detections),
                "classes_count": count_classes(detections),
                "image_size": f"{img.shape[1]}x{img.shape[0]}"
            },
            "config": {
                "confidence_threshold": conf,
                "detection_ids": list(range(1, len(detections) + 1))
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据库保存失败: {str(e)}")
    finally:
        db.close()


@router.post("/detect/image/custom")
async def detect_image_custom(
        file: UploadFile = File(...),
        conf: float = 0.25,
        hidden_ids: str = ""  # 前端传入的要隐藏的框ID列表，如 "1,3,5"
):
    """
    自定义显示/隐藏检测框的接口
    """
    # 解析要隐藏的框ID
    hidden_id_list = []
    if hidden_ids:
        try:
            hidden_id_list = [int(id.strip()) for id in hidden_ids.split(",")]
        except:
            pass

    # 文件处理（同上）
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".bmp"]:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # 运行推理
    results = model.predict(source=save_path, imgsz=1280, conf=conf, save=False, verbose=False)
    r = results[0]
    img = cv2.imread(save_path)

    if img is None:
        raise HTTPException(status_code=500, detail="无法读取图片文件")

    detections = []
    detection_id = 1

    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls_ids = r.boxes.cls.cpu().numpy().astype(int)

        for i, (box, confs_i, cls_i) in enumerate(zip(boxes, confs, cls_ids)):
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls_i)]

            # 检查当前框是否应该隐藏
            is_visible = detection_id not in hidden_id_list
            color = get_color_by_class_and_id(label, detection_id)

            detection_info = {
                "id": detection_id,
                "class": label,
                "confidence": float(confs_i),
                "bbox": [x1, y1, x2, y2],
                "color": color,
                "visible": is_visible,
                "area": (x2 - x1) * (y2 - y1)
            }
            detections.append(detection_info)

            # 只绘制可见的框
            if is_visible:
                draw_detection_box(img, detection_info)

            detection_id += 1

    # 保存结果
    out_name = f"res_custom_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    return {
        "result_url": f"/api/files/result/{out_name}",
        "detections": detections,
        "hidden_ids": hidden_id_list,
        "visible_count": len([d for d in detections if d["visible"]]),
        "hidden_count": len(hidden_id_list)
    }


@router.post("/detect/image/preview")
async def preview_detection(
        file: UploadFile = File(...),
        hidden_ids: str = "",
        conf: float = 0.25
):
    """
    实时预览接口 - 返回base64图片，用于前端实时预览
    """
    # 解析隐藏的ID
    hidden_id_list = [int(id.strip()) for id in hidden_ids.split(",")] if hidden_ids else []

    # 处理图片
    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="无法解码图片")

    # 临时保存用于推理
    temp_path = f"/tmp/temp_{int(time.time())}.jpg"
    cv2.imwrite(temp_path, img)

    # 运行推理
    results = model.predict(source=temp_path, imgsz=1280, conf=conf, save=False, verbose=False)
    r = results[0]

    detections = []
    detection_id = 1

    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls_ids = r.boxes.cls.cpu().numpy().astype(int)

        for i, (box, confs_i, cls_i) in enumerate(zip(boxes, confs, cls_ids)):
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls_i)]

            is_visible = detection_id not in hidden_id_list
            color = get_color_by_class_and_id(label, detection_id)

            detection_info = {
                "id": detection_id,
                "class": label,
                "confidence": float(confs_i),
                "bbox": [x1, y1, x2, y2],
                "color": color,
                "visible": is_visible
            }
            detections.append(detection_info)

            if is_visible:
                draw_detection_box(img, detection_info)

            detection_id += 1

    # 转换为base64返回
    _, buffer = cv2.imencode('.jpg', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')

    # 清理临时文件
    if os.path.exists(temp_path):
        os.remove(temp_path)

    return {
        "image": f"data:image/jpeg;base64,{img_base64}",
        "detections": detections,
        "hidden_ids": hidden_id_list
    }


@router.get("/files/result/{filename}")
def get_result_file(filename: str):
    """获取结果文件"""
    p = os.path.join(RESULT_DIR, filename)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(p)


# ========== 工具函数 ==========

def get_color_by_class_and_id(class_name: str, detection_id: int):
    """根据类别和ID生成颜色"""
    # 基础颜色映射
    base_colors = {
        'person': (0, 255, 0),  # 绿色 - 行人
        'car': (255, 0, 0),  # 蓝色 - 汽车
        'bicycle': (0, 255, 255),  # 黄色 - 自行车
        'motorcycle': (255, 255, 0),  # 青色 - 摩托车
    }

    # 获取基础颜色
    base_color = base_colors.get(class_name, (128, 128, 128))

    # 根据ID微调颜色，使每个框都有轻微差异
    r = min(255, max(0, base_color[0] + (detection_id * 30) % 100))
    g = min(255, max(0, base_color[1] + (detection_id * 50) % 100))
    b = min(255, max(0, base_color[2] + (detection_id * 70) % 100))

    return (int(r), int(g), int(b))


def draw_detection_box(img, detection_info):
    """绘制带编号的检测框"""
    x1, y1, x2, y2 = detection_info["bbox"]
    color = detection_info["color"]
    label = detection_info["class"]
    confidence = detection_info["confidence"]
    box_id = detection_info["id"]

    # 绘制边界框
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

    # 创建标签文本
    label_text = f"{box_id}:{label} {confidence:.2f}"

    # 计算文本大小
    label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

    # 绘制标签背景
    cv2.rectangle(img, (x1, y1 - label_size[1] - 10),
                  (x1 + label_size[0] + 10, y1), color, -1)

    # 绘制标签文字
    cv2.putText(img, label_text, (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def count_classes(detections):
    """统计各类别数量"""
    class_count = {}
    for detection in detections:
        class_name = detection["class"]
        class_count[class_name] = class_count.get(class_name, 0) + 1
    return class_count


@router.get("/detect/image/{record_id}/toggle")
async def toggle_detection_visibility(record_id: int, detection_id: int, visible: bool = True):
    """
    切换单个检测框的显示状态
    """
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        # 解析检测结果
        detections = json.loads(record.objects) if record.objects else []

        # 更新指定检测框的可见性
        for detection in detections:
            if detection.get("id") == detection_id:
                detection["visible"] = visible
                break

        # 更新记录
        record.objects = json.dumps(detections)
        db.commit()

        return {"success": True, "detection_id": detection_id, "visible": visible}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
    finally:
        db.close()