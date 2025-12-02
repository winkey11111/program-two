from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import time
import aiofiles
import json
from typing import List, Dict, Any
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord, Base
from ultralytics import YOLO
import cv2
import numpy as np
import base64

router = APIRouter()
model = YOLO(MODEL_PATH)


# 初始化数据库表
def init_db():
    from db import engine
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("detect_record")]
    if "result_url" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE detect_record ADD COLUMN result_url TEXT"))
            conn.commit()


init_db()


@router.post("/detect/image")
async def detect_image(file: UploadFile = File(...), conf: float = 0.25):
    """
    增强的图像检测接口 - 支持框编号和自定义显示
    """
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".bmp"]:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

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

        for box, confs_i, cls_i in zip(boxes, confs, cls_ids):
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls_i)]
            color = get_color_by_class_and_id(label, detection_id)

            detection_info = {
                "id": detection_id,
                "class": label,
                "confidence": float(confs_i),
                "bbox": [x1, y1, x2, y2],
                "color": color,
                "visible": True,
                "area": (x2 - x1) * (y2 - y1)
            }
            detections.append(detection_info)
            draw_detection_box(img, detection_info)
            detection_id += 1

    out_name = f"res_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    db = SessionLocal()
    try:
        record = DetectRecord(
            type="image",
            filename=save_name,
            source_path=save_path,
            result_path=out_path,
            result_url=f"/files/result/{out_name}",  # ✅ 关键：保存 result_url
            objects=json.dumps(detections)
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            "id": record.id,
            "result_url": f"/files/result/{out_name}",
            "detections": detections,
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
    hidden_ids: str = ""
):
    """
    自定义显示/隐藏检测框的接口
    """
    hidden_id_list = []
    if hidden_ids:
        try:
            hidden_id_list = [int(id.strip()) for id in hidden_ids.split(",")]
        except ValueError:
            pass

    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".bmp"]:
        raise HTTPException(status_code=400, detail="不支持的图片格式")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

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

        for box, confs_i, cls_i in zip(boxes, confs, cls_ids):
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
                "visible": is_visible,
                "area": (x2 - x1) * (y2 - y1)
            }
            detections.append(detection_info)
            if is_visible:
                draw_detection_box(img, detection_info)
            detection_id += 1

    out_name = f"res_custom_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    return {
        "result_url": f"/files/result/{out_name}",  # ✅ 修正：去掉 /api 前缀
        "detections": detections,
        "hidden_ids": hidden_id_list,
        "visible_count": len([d for d in detections if d["visible"]]),
        "hidden_count": len(hidden_id_list)
    }


@router.post("/detect/image/preview")
async def preview_detection(file: UploadFile = File(...), hidden_ids: str = "", conf: float = 0.25):
    """
    实时预览接口 - 返回 base64 图片
    """
    hidden_id_list = [int(id.strip()) for id in hidden_ids.split(",")] if hidden_ids else []

    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解码图片")

    temp_path = f"/tmp/temp_{int(time.time())}.jpg"
    cv2.imwrite(temp_path, img)

    results = model.predict(source=temp_path, imgsz=1280, conf=conf, save=False, verbose=False)
    r = results[0]

    detections = []
    detection_id = 1

    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls_ids = r.boxes.cls.cpu().numpy().astype(int)

        for box, confs_i, cls_i in zip(boxes, confs, cls_ids):
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

    _, buffer = cv2.imencode('.jpg', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')

    if os.path.exists(temp_path):
        os.remove(temp_path)

    return {
        "image": f"data:image/jpeg;base64,{img_base64}",
        "detections": detections,
        "hidden_ids": hidden_id_list
    }


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

        detections = json.loads(record.objects) if record.objects else []
        for detection in detections:
            if detection.get("id") == detection_id:
                detection["visible"] = visible
                break

        record.objects = json.dumps(detections)
        db.commit()

        return {"success": True, "detection_id": detection_id, "visible": visible}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
    finally:
        db.close()


# ========== 工具函数 ==========

def get_color_by_class_and_id(class_name: str, detection_id: int):
    base_colors = {
        'person': (0, 255, 0),
        'car': (255, 0, 0),
        'bicycle': (0, 255, 255),
        'motorcycle': (255, 255, 0),
    }
    base_color = base_colors.get(class_name, (128, 128, 128))
    r = min(255, max(0, base_color[0] + (detection_id * 30) % 100))
    g = min(255, max(0, base_color[1] + (detection_id * 50) % 100))
    b = min(255, max(0, base_color[2] + (detection_id * 70) % 100))
    return (int(r), int(g), int(b))


def draw_detection_box(img, detection_info):
    x1, y1, x2, y2 = detection_info["bbox"]
    color = detection_info["color"]
    label = detection_info["class"]
    confidence = detection_info["confidence"]
    box_id = detection_info["id"]

    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    label_text = f"{box_id}:{label} {confidence:.2f}"
    label_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.rectangle(img, (x1, y1 - label_size[1] - 10), (x1 + label_size[0] + 10, y1), color, -1)
    cv2.putText(img, label_text, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def count_classes(detections):
    class_count = {}
    for detection in detections:
        class_name = detection["class"]
        class_count[class_name] = class_count.get(class_name, 0) + 1
    return class_count