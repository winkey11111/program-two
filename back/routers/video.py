# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
import os
import time
import aiofiles
import json
import re
from typing import List, Dict, Any
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord
from ultralytics import YOLO
import cv2
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

try:
    model = YOLO(MODEL_PATH)
    logger.info(f"✅ 模型加载成功，支持 {len(model.names)} 个类别: {model.names}")
except Exception as e:
    logger.error(f"❌ 模型加载失败: {e}")
    model = None

video_detection_data: Dict[str, Any] = {}


def sanitize_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)


def _is_safe_path(base_dir: str, path: str) -> bool:
    try:
        base_real = os.path.realpath(base_dir)
        path_real = os.path.realpath(path)
        return os.path.commonpath([base_real, path_real]) == base_real
    except Exception:
        return False


# ========== 文件访问路由 ==========

@router.get("/files/upload/{filename}")
async def get_upload_file(filename: str):
    safe_name = sanitize_filename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    if not _is_safe_path(UPLOAD_DIR, file_path) or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


@router.get("/files/result/{filename}")
async def get_result_file(filename: str):
    safe_name = sanitize_filename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    file_path = os.path.join(RESULT_DIR, safe_name)
    if not _is_safe_path(RESULT_DIR, file_path) or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


# ========== 视频处理核心函数 ==========

def process_video_with_controls(input_path: str, output_path: str, conf_threshold: float = 0.5):
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载成功")

    logger.info(f"🚀 开始视频处理: {input_path}")
    start_time = time.time()

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="无法打开视频文件")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    results = model.track(
        source=input_path,
        imgsz=1280,
        conf=conf_threshold,
        iou=0.5,
        persist=True,
        tracker="bytetrack.yaml",
        verbose=False,
        stream=True
    )

    active_tracks = {}
    track_id_to_display_id = {}
    next_display_id = 1
    frame_detections = []

    for frame_idx, result in enumerate(results):
        frame = result.orig_img.copy()
        frame_detection_data = {
            "frame_index": frame_idx,
            "detections": [],
            "timestamp": frame_idx / fps if fps > 0 else frame_idx / 25
        }

        if result.boxes is not None and result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            track_ids = result.boxes.id.cpu().numpy().astype(int)
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)

            for box, track_id, conf, class_id in zip(boxes, track_ids, confidences, class_ids):
                x1, y1, x2, y2 = map(int, box)
                class_name = model.names[int(class_id)]
                bbox_area = (x2 - x1) * (y2 - y1)
                if bbox_area < 300 or conf < conf_threshold:
                    continue

                if track_id not in track_id_to_display_id:
                    track_id_to_display_id[track_id] = next_display_id
                    next_display_id += 1

                display_id = track_id_to_display_id[track_id]
                color = get_color_by_class_and_id(class_name, display_id)

                detection_info = {
                    "id": display_id,
                    "track_id": int(track_id),
                    "class": class_name,
                    "confidence": float(conf),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "color": color,
                    "area": bbox_area,
                    "visible": True
                }

                frame_detection_data["detections"].append(detection_info)
                draw_detection_box(frame, detection_info)
                active_tracks[track_id] = {
                    'class': class_name,
                    'last_seen': frame_idx,
                    'display_id': display_id,
                    'current_bbox': [x1, y1, x2, y2]
                }

        draw_frame_stats(frame, frame_idx, len(frame_detection_data["detections"]),
                         total_frames, fps, w)
        frame_detections.append(frame_detection_data)
        out.write(frame)

        if frame_idx % 100 == 0:
            logger.info(f"📊 处理进度: {frame_idx}/{total_frames} 帧")

    processing_time = time.time() - start_time
    cap.release()
    out.release()

    video_id = os.path.splitext(os.path.basename(output_path))[0]
    video_detection_data[video_id] = {
        "detections": frame_detections,
        "video_info": {
            "width": w,
            "height": h,
            "fps": fps,
            "total_frames": total_frames,
            "processing_time": processing_time,
            "total_tracks": len(track_id_to_display_id)
        },
        "display_settings": {
            "visible_ids": list(range(1, next_display_id)),
            "hidden_ids": []
        }
    }

    logger.info(f"✅ 视频处理完成! 总跟踪目标: {len(track_id_to_display_id)}")
    return {
        "video_id": video_id,
        "total_frames": total_frames,
        "total_tracks": len(track_id_to_display_id),
        "processing_time": processing_time,
    }


def regenerate_video_with_controls(video_id: str, hidden_ids: List[int],
                                   input_path: str, output_path: str):
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频数据不存在")

    detection_data = video_detection_data[video_id]
    frame_detections = detection_data["detections"]
    video_info = detection_data["video_info"]

    cap = cv2.VideoCapture(input_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, video_info["fps"],
                          (video_info["width"], video_info["height"]))

    for frame_data in frame_detections:
        ret, frame = cap.read()
        if not ret:
            break

        for detection in frame_data["detections"]:
            if detection["id"] not in hidden_ids:
                draw_detection_box(frame, detection)

        visible_count = len([d for d in frame_data["detections"] if d["id"] not in hidden_ids])
        draw_frame_stats_with_controls(frame, frame_data["frame_index"], visible_count,
                                       len(frame_data["detections"]), hidden_ids,
                                       video_info["total_frames"], video_info["fps"],
                                       video_info["width"])
        out.write(frame)

    cap.release()
    out.release()

    video_detection_data[video_id]["display_settings"] = {
        "visible_ids": [i for i in range(1, video_info["total_tracks"] + 1) if i not in hidden_ids],
        "hidden_ids": hidden_ids
    }

    logger.info(f"✅ 视频重新生成完成! 隐藏了 {len(hidden_ids)} 个框")


def get_color_by_class_and_id(class_name: str, display_id: int):
    base_colors = {
        'person': (0, 255, 0),
        'car': (255, 0, 0),
        'bicycle': (0, 255, 255),
        'motorcycle': (255, 255, 0),
    }
    base_color = base_colors.get(class_name, (128, 128, 128))
    r = min(255, max(0, base_color[0] + (display_id * 30) % 100))
    g = min(255, max(0, base_color[1] + (display_id * 50) % 100))
    b = min(255, max(0, base_color[2] + (display_id * 70) % 100))
    return (int(r), int(g), int(b))


def draw_detection_box(img, detection_info):
    x1, y1, x2, y2 = detection_info["bbox"]
    color = detection_info["color"]
    class_name = detection_info["class"]
    confidence = detection_info["confidence"]
    box_id = detection_info["id"]

    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    label = f"{box_id}:{class_name} {confidence:.2f}"
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.rectangle(img, (x1, y1 - label_size[1] - 10),
                  (x1 + label_size[0] + 10, y1), color, -1)
    cv2.putText(img, label, (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_frame_stats(img, frame_idx, detection_count, total_frames, fps, width):
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
    progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0
    stats_text = f"帧: {frame_idx} ({progress:.1f}%) | 检测: {detection_count}"
    cv2.putText(img, stats_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_frame_stats_with_controls(img, frame_idx, visible_count, total_count,
                                   hidden_ids, total_frames, fps, width):
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
    progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0
    stats_text = f"帧: {frame_idx} ({progress:.1f}%) | 可见: {visible_count}/{total_count}"
    cv2.putText(img, stats_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    control_text = f"隐藏框: {len(hidden_ids)}个"
    cv2.putText(img, control_text, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
    if hidden_ids:
        hidden_text = f"隐藏ID: {','.join(map(str, hidden_ids[:5]))}{'...' if len(hidden_ids) > 5 else ''}"
        cv2.putText(img, hidden_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)


# ========== 视频处理路由 ==========

def _validate_video_id(video_id: str):
    if not re.match(r"^[a-zA-Z0-9_-]+$", video_id):
        raise HTTPException(status_code=400, detail="无效的 video_id")


@router.post("/detect/video")
async def detect_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    conf: float = 0.5
):
    if conf < 0 or conf > 1:
        raise HTTPException(status_code=400, detail="置信度应在 0~1 之间")

    filename = sanitize_filename(file.filename)
    name_no_ext, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="不支持的视频格式")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{name_no_ext}{ext}"
    out_name = f"res_{timestamp}_{name_no_ext}.mp4"

    save_path = os.path.join(UPLOAD_DIR, save_name)
    out_path = os.path.join(RESULT_DIR, out_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    def _bg_task():
        try:
            result_info = process_video_with_controls(save_path, out_path, conf_threshold=conf)
            video_id = result_info["video_id"]

            db = SessionLocal()
            try:
                record = DetectRecord(
                    type="video",
                    filename=save_name,
                    source_path=save_path,
                    result_path=out_path,
                    objects=json.dumps({
                        "video_id": video_id,
                        "total_tracks": result_info["total_tracks"],
                        "processing_time": result_info["processing_time"]
                    })
                )
                db.add(record)
                db.commit()
                logger.info(f"💾 数据库记录已保存，记录ID: {record.id}")
            except Exception as db_error:
                logger.error(f"❌ 数据库保存失败: {db_error}")
                db.rollback()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"❌ 处理视频时出错: {e}")
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass

    if background_tasks:
        background_tasks.add_task(_bg_task)
    else:
        _bg_task()

    return {
        "status": "processing",
        "result_url": f"/api/files/result/{out_name}",
        "message": "视频正在处理中，处理完成后可控制框的显示",
        "features": {
            "box_controls": True,
            "realtime_toggle": True,
            "confidence_threshold": conf
        }
    }


@router.post("/video/{video_id}/toggle-boxes")
async def toggle_video_boxes(
    video_id: str,
    hidden_ids: List[int] = Query(...),
    regenerate: bool = False
):
    _validate_video_id(video_id)
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    current_info = video_detection_data[video_id]["video_info"]
    max_id = current_info["total_tracks"]
    invalid_ids = [hid for hid in hidden_ids if hid < 1 or hid > max_id]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"无效的隐藏ID: {invalid_ids}")

    if regenerate:
        source_path = None
        db = SessionLocal()
        try:
            record = db.query(DetectRecord).filter(
                DetectRecord.result_path.like(f"%{video_id}%")
            ).first()
            if record and os.path.exists(record.source_path):
                source_path = record.source_path
        finally:
            db.close()

        if not source_path or not os.path.exists(source_path):
            raise HTTPException(status_code=404, detail="原始视频文件不存在")

        new_out_name = f"res_{video_id}_controlled.mp4"
        new_out_path = os.path.join(RESULT_DIR, new_out_name)
        regenerate_video_with_controls(video_id, hidden_ids, source_path, new_out_path)

        return {
            "status": "regenerated",
            "new_video_url": f"/api/files/result/{new_out_name}",
            "hidden_ids": hidden_ids,
            "visible_count": max_id - len(hidden_ids),
            "hidden_count": len(hidden_ids)
        }
    else:
        video_detection_data[video_id]["display_settings"] = {
            "visible_ids": [i for i in range(1, max_id + 1) if i not in hidden_ids],
            "hidden_ids": hidden_ids
        }
        return {
            "status": "updated",
            "hidden_ids": hidden_ids,
            "visible_ids": video_detection_data[video_id]["display_settings"]["visible_ids"],
            "message": "显示设置已更新"
        }


@router.get("/video/{video_id}/detections")
async def get_video_detections(video_id: str, frame_index: int = None):
    _validate_video_id(video_id)
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    detection_data = video_detection_data[video_id]
    hidden_ids = detection_data["display_settings"]["hidden_ids"]

    if frame_index is not None:
        if not (0 <= frame_index < len(detection_data["detections"])):
            raise HTTPException(status_code=404, detail="帧索引超出范围")
        frame_data = detection_data["detections"][frame_index].copy()
        frame_data["detections"] = [d for d in frame_data["detections"] if d["id"] not in hidden_ids]
        frame_data["visible_count"] = len(frame_data["detections"])
        return frame_data
    else:
        return {
            "video_id": video_id,
            "total_frames": len(detection_data["detections"]),
            "total_tracks": detection_data["video_info"]["total_tracks"],
            "display_settings": detection_data["display_settings"],
            "video_info": detection_data["video_info"]
        }


@router.get("/video/{video_id}/objects")
async def get_video_objects(video_id: str):
    _validate_video_id(video_id)
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    detection_data = video_detection_data[video_id]
    objects = {}

    for frame_data in detection_data["detections"]:
        for detection in frame_data["detections"]:
            obj_id = detection["id"]
            if obj_id not in objects:
                objects[obj_id] = {
                    "id": obj_id,
                    "class": detection["class"],
                    "first_seen": frame_data["timestamp"],
                    "appearances": 0,
                    "color": detection["color"]
                }
            objects[obj_id]["appearances"] += 1

    return {
        "video_id": video_id,
        "objects": list(objects.values()),
        "total_objects": len(objects)
    }


@router.post("/video/{video_id}/reset")
async def reset_video_boxes(video_id: str):
    _validate_video_id(video_id)
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    total_tracks = video_detection_data[video_id]["video_info"]["total_tracks"]
    video_detection_data[video_id]["display_settings"] = {
        "visible_ids": list(range(1, total_tracks + 1)),
        "hidden_ids": []
    }
    return {
        "status": "reset",
        "message": "已重置所有框为可见状态",
        "visible_count": total_tracks
    }