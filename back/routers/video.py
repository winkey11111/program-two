# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import os
import time
import aiofiles
import shutil
import json
from typing import List, Dict, Any, Optional
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord, Base
from ultralytics import YOLO
import cv2
import numpy as np
from collections import defaultdict, deque
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

# 加载模型
try:
    model = YOLO(MODEL_PATH)
    logger.info(f"✅ 模型加载成功，支持 {len(model.names)} 个类别: {model.names}")
except Exception as e:
    logger.error(f"❌ 模型加载失败: {e}")
    model = None

# 全局存储检测数据（生产环境建议用数据库或Redis）
video_detection_data = {}


def process_video_with_controls(input_path: str, output_path: str, conf: float = 0.5):
    """
    支持前端控制框显示的视频处理函数
    """
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载成功")

    logger.info(f"🚀 开始视频处理（支持框控制）: {input_path}")
    start_time = time.time()

    # 打开输入视频
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="无法打开视频文件")

    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"📊 视频信息: {w}x{h}, FPS: {fps}, 总帧数: {total_frames}")

    # 创建输出视频
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    # 视频处理结果
    results = model.track(
        source=input_path,
        imgsz=1280,
        conf=conf,
        iou=0.5,
        persist=True,
        tracker="bytetrack.yaml",
        verbose=False,
        stream=True
    )

    # 跟踪状态管理
    active_tracks = {}
    track_id_to_display_id = {}
    next_display_id = 1
    frame_detections = []  # 存储每帧的检测数据

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

            # 处理当前帧的检测结果
            for i, (box, track_id, conf, class_id) in enumerate(zip(boxes, track_ids, confidences, class_ids)):
                x1, y1, x2, y2 = map(int, box)
                class_name = model.names[int(class_id)]

                # 过滤条件
                bbox_area = (x2 - x1) * (y2 - y1)
                if bbox_area < 300 or conf < conf * 0.8:
                    continue

                # 管理显示ID
                if track_id not in track_id_to_display_id:
                    track_id_to_display_id[track_id] = next_display_id
                    next_display_id += 1

                display_id = track_id_to_display_id[track_id]
                color = get_color_by_class_and_id(class_name, display_id)

                # 检测框信息（用于前端控制）
                detection_info = {
                    "id": display_id,  # 显示ID（前端控制用）
                    "track_id": int(track_id),  # 跟踪ID
                    "class": class_name,
                    "confidence": float(conf),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "color": color,
                    "area": bbox_area,
                    "visible": True  # 默认可见
                }

                # 添加到帧检测数据
                frame_detection_data["detections"].append(detection_info)

                # 绘制检测框（默认全部绘制）
                draw_detection_box(frame, detection_info)

                # 更新活跃轨迹
                active_tracks[track_id] = {
                    'class': class_name,
                    'last_seen': frame_idx,
                    'display_id': display_id,
                    'current_bbox': [x1, y1, x2, y2]
                }

        # 绘制统计信息
        draw_frame_stats(frame, frame_idx, len(frame_detection_data["detections"]),
                         total_frames, fps, w)

        frame_detections.append(frame_detection_data)
        out.write(frame)

        if frame_idx % 100 == 0:
            logger.info(f"📊 处理进度: {frame_idx}/{total_frames} frames, "
                        f"检测到 {len(frame_detection_data['detections'])} 个目标")

    # 计算处理时间
    processing_time = time.time() - start_time

    cap.release()
    out.release()

    # 生成视频的唯一标识
    video_id = os.path.splitext(os.path.basename(output_path))[0]

    # 存储检测数据（生产环境应使用数据库）
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
            "visible_ids": list(range(1, next_display_id)),  # 所有ID默认可见
            "hidden_ids": []  # 隐藏的ID列表
        }
    }

    logger.info(f"✅ 视频处理完成! 总跟踪目标: {len(track_id_to_display_id)}")

    return {
        "video_id": video_id,
        "total_frames": total_frames,
        "total_tracks": len(track_id_to_display_id),
        "processing_time": processing_time,
        "detection_data": {
            "total_detections": sum(len(f["detections"]) for f in frame_detections),
            "unique_objects": len(track_id_to_display_id)
        }
    }


def regenerate_video_with_controls(video_id: str, hidden_ids: List[int],
                                   input_path: str, output_path: str):
    """
    根据隐藏的ID重新生成视频
    """
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频数据不存在")

    detection_data = video_detection_data[video_id]
    frame_detections = detection_data["detections"]
    video_info = detection_data["video_info"]

    logger.info(f"🔄 重新生成视频 {video_id}, 隐藏ID: {hidden_ids}")

    # 打开原始视频
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="无法打开原始视频")

    # 创建新输出视频
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, video_info["fps"],
                          (video_info["width"], video_info["height"]))

    for frame_idx, frame_data in enumerate(frame_detections):
        ret, frame = cap.read()
        if not ret:
            break

        # 绘制可见的检测框
        for detection in frame_data["detections"]:
            if detection["id"] not in hidden_ids:  # 只绘制未隐藏的框
                draw_detection_box(frame, detection)

        # 绘制统计信息（显示隐藏状态）
        visible_count = len([d for d in frame_data["detections"] if d["id"] not in hidden_ids])
        draw_frame_stats_with_controls(frame, frame_idx, visible_count,
                                       len(frame_data["detections"]), hidden_ids,
                                       video_info["total_frames"], video_info["fps"],
                                       video_info["width"])

        out.write(frame)

    cap.release()
    out.release()

    # 更新显示设置
    video_detection_data[video_id]["display_settings"] = {
        "visible_ids": [i for i in range(1, video_info["total_tracks"] + 1)
                        if i not in hidden_ids],
        "hidden_ids": hidden_ids
    }

    logger.info(f"✅ 视频重新生成完成! 隐藏了 {len(hidden_ids)} 个框")


@router.post("/detect/video")
async def detect_video(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        conf: float = 0.5
):
    """
    支持框控制的视频检测接口
    """
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="不支持的视频格式")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    # 确保目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(RESULT_DIR, exist_ok=True)

    # 保存上传的文件
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # 准备输出路径
    out_name = f"res_{save_name}.mp4"
    out_path = os.path.join(RESULT_DIR, out_name)

    def _bg_task():
        """后台处理任务"""
        try:
            logger.info("🔧 开始视频处理任务...")

            # 处理视频
            result_info = process_video_with_controls(save_path, out_path, conf=conf)
            video_id = result_info["video_id"]

            # 保存到数据库
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
                db.refresh(record)
                logger.info(f"💾 数据库记录已保存，记录ID: {record.id}")
            except Exception as db_error:
                logger.error(f"❌ 数据库保存失败: {db_error}")
                db.rollback()
            finally:
                db.close()

            logger.info(f"✅ 视频处理完成: {out_path}")

        except Exception as e:
            logger.error(f"❌ 处理视频时出错: {e}")
            # 清理临时文件
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except:
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
        hidden_ids: List[int] = Query(..., description="要隐藏的框ID列表"),
        regenerate: bool = False
):
    """
    切换视频中框的显示状态
    """
    if video_id not in video_detection_data:
        # 尝试从文件名查找
        video_file = f"{video_id}.mp4"
        video_path = os.path.join(RESULT_DIR, video_file)

        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="视频不存在")

        # 这里可以添加从数据库恢复检测数据的逻辑
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    # 更新显示设置
    current_settings = video_detection_data[video_id]["display_settings"]
    current_settings["hidden_ids"] = hidden_ids
    current_settings["visible_ids"] = [
        i for i in range(1, video_detection_data[video_id]["video_info"]["total_tracks"] + 1)
        if i not in hidden_ids
    ]

    if regenerate:
        # 重新生成视频
        input_path = video_detection_data[video_id].get("source_path", "")
        if not input_path or not os.path.exists(input_path):
            raise HTTPException(status_code=404, detail="原始视频文件不存在")

        # 生成新版本视频
        new_out_name = f"res_{video_id}_controlled.mp4"
        new_out_path = os.path.join(RESULT_DIR, new_out_name)

        regenerate_video_with_controls(video_id, hidden_ids, input_path, new_out_path)

        return {
            "status": "regenerated",
            "new_video_url": f"/api/files/result/{new_out_name}",
            "hidden_ids": hidden_ids,
            "visible_count": len(current_settings["visible_ids"]),
            "hidden_count": len(hidden_ids)
        }
    else:
        return {
            "status": "updated",
            "hidden_ids": hidden_ids,
            "visible_ids": current_settings["visible_ids"],
            "message": "显示设置已更新，下次播放时将应用新设置"
        }


@router.get("/video/{video_id}/detections")
async def get_video_detections(video_id: str, frame_index: int = None):
    """
    获取视频的检测数据
    """
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    detection_data = video_detection_data[video_id]

    if frame_index is not None:
        # 返回指定帧的检测数据
        if 0 <= frame_index < len(detection_data["detections"]):
            frame_data = detection_data["detections"][frame_index]
            hidden_ids = detection_data["display_settings"]["hidden_ids"]

            # 过滤掉隐藏的框
            frame_data["detections"] = [
                d for d in frame_data["detections"]
                if d["id"] not in hidden_ids
            ]
            frame_data["visible_count"] = len(frame_data["detections"])

            return frame_data
        else:
            raise HTTPException(status_code=404, detail="帧索引超出范围")
    else:
        # 返回摘要信息
        return {
            "video_id": video_id,
            "total_frames": len(detection_data["detections"]),
            "total_tracks": detection_data["video_info"]["total_tracks"],
            "display_settings": detection_data["display_settings"],
            "video_info": detection_data["video_info"]
        }


@router.get("/video/{video_id}/objects")
async def get_video_objects(video_id: str):
    """
    获取视频中所有出现的物体列表
    """
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
    """
    重置视频框显示（显示所有框）
    """
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频检测数据不存在")

    video_detection_data[video_id]["display_settings"] = {
        "visible_ids": list(range(1, video_detection_data[video_id]["video_info"]["total_tracks"] + 1)),
        "hidden_ids": []
    }

    return {
        "status": "reset",
        "message": "已重置所有框为可见状态",
        "visible_count": video_detection_data[video_id]["video_info"]["total_tracks"]
    }


# ========== 工具函数 ==========

def get_color_by_class_and_id(class_name: str, display_id: int):
    """根据类别和ID生成颜色"""
    base_colors = {
        'person': (0, 255, 0),  # 绿色
        'car': (255, 0, 0),  # 蓝色
        'bicycle': (0, 255, 255),  # 黄色
        'motorcycle': (255, 255, 0),  # 青色
    }
    base_color = base_colors.get(class_name, (128, 128, 128))

    # 根据ID微调颜色
    r = min(255, max(0, base_color[0] + (display_id * 30) % 100))
    g = min(255, max(0, base_color[1] + (display_id * 50) % 100))
    b = min(255, max(0, base_color[2] + (display_id * 70) % 100))

    return (int(r), int(g), int(b))


def draw_detection_box(img, detection_info):
    """绘制检测框"""
    x1, y1, x2, y2 = detection_info["bbox"]
    color = detection_info["color"]
    class_name = detection_info["class"]
    confidence = detection_info["confidence"]
    box_id = detection_info["id"]

    # 绘制边界框
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

    # 创建标签
    label = f"{box_id}:{class_name} {confidence:.2f}"
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

    # 标签背景
    cv2.rectangle(img, (x1, y1 - label_size[1] - 10),
                  (x1 + label_size[0] + 10, y1), color, -1)

    # 标签文字
    cv2.putText(img, label, (x1 + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_frame_stats(img, frame_idx, detection_count, total_frames, fps, width):
    """绘制帧统计信息"""
    progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0

    # 背景
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

    # 统计信息
    stats_text = f"帧: {frame_idx} ({progress:.1f}%) | 检测: {detection_count}"
    cv2.putText(img, stats_text, (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_frame_stats_with_controls(img, frame_idx, visible_count, total_count,
                                   hidden_ids, total_frames, fps, width):
    """绘制带控制状态的帧统计信息"""
    progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0

    # 背景
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (width, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

    # 统计信息
    stats_text = f"帧: {frame_idx} ({progress:.1f}%) | 可见: {visible_count}/{total_count}"
    cv2.putText(img, stats_text, (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # 控制状态
    control_text = f"隐藏框: {len(hidden_ids)}个"
    cv2.putText(img, control_text, (10, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)

    if hidden_ids:
        hidden_text = f"隐藏ID: {','.join(map(str, hidden_ids[:5]))}{'...' if len(hidden_ids) > 5 else ''}"
        cv2.putText(img, hidden_text, (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)


@router.get("/files/result/{filename}")
async def get_result_file(filename: str):
    """获取结果文件"""
    file_path = os.path.join(RESULT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)