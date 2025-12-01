# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import os
import time
import aiofiles
import shutil
import json
import subprocess
from typing import List, Dict, Any, Optional
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH, TRANSCODED_DIR
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
    logger.error(f"❌❌ 模型加载失败: {e}")
    model = None

# 全局存储检测数据（生产环境建议用数据库或Redis）
video_detection_data = {}

# 确保转码目录存在
os.makedirs(TRANSCODED_DIR, exist_ok=True)


def transcode_video(input_path: str, output_path: str) -> bool:
    """
    使用ffmpeg转码视频，提高兼容性和压缩率
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            logger.error(f"❌ 输入视频文件不存在: {input_path}")
            return False

        # ffmpeg转码命令
        # 使用H.264编码，兼容性更好的设置
        cmd = [
            'ffmpeg',
            '-i', input_path,  # 输入文件
            '-c:v', 'libx264',  # 视频编码器
            '-preset', 'medium',  # 编码速度与压缩率的平衡
            '-crf', '23',  # 恒定质量因子（0-51，越小质量越好）
            '-c:a', 'aac',  # 音频编码器
            '-b:a', '128k',  # 音频比特率
            '-movflags', '+faststart',  # 优化网络播放
            '-y',  # 覆盖输出文件
            output_path  # 输出文件
        ]

        logger.info(f"🔄 开始视频转码: {input_path} -> {output_path}")
        logger.info(f"📋 转码命令: {' '.join(cmd)}")

        # 执行转码
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1小时超时

        if result.returncode == 0:
            # 检查输出文件大小
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                input_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
                output_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0

                logger.info(f"✅ 视频转码成功!")
                logger.info(f"📊 文件大小: {input_size:.2f}MB -> {output_size:.2f}MB")
                logger.info(f"💾 压缩率: {compression_ratio:.1f}%")
                return True
            else:
                logger.error("❌ 转码后文件为空或不存在")
                return False
        else:
            logger.error(f"❌ ffmpeg转码失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ 视频转码超时（超过1小时）")
        return False
    except Exception as e:
        logger.error(f"❌ 转码过程异常: {str(e)}")
        return False


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    获取视频文件信息
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {}
    except:
        return {}


def process_video_with_controls(input_path: str, output_path: str, conf: float = 0.5):
    """
    支持前端控制框显示的视频处理函数，包含转码功能
    """
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载成功")

    logger.info(f"🚀🚀 开始视频处理（支持框控制）: {input_path}")
    start_time = time.time()

    # 打开输入视频
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="无法打开视频文件")

    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"📊📊 视频信息: {w}x{h}, FPS: {fps}, 总帧数: {total_frames}")

    # 创建输出视频（原始处理结果）
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
            logger.info(f"📊📊 处理进度: {frame_idx}/{total_frames} frames, "
                        f"检测到 {len(frame_detection_data['detections'])} 个目标")

    # 计算处理时间
    processing_time = time.time() - start_time

    cap.release()
    out.release()

    # 生成转码后的视频路径
    original_filename = os.path.splitext(os.path.basename(output_path))[0]
    transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{original_filename}.mp4")

    # 进行视频转码
    logger.info("🎬 开始视频转码...")
    transcode_success = transcode_video(output_path, transcoded_path)

    if transcode_success:
        logger.info(f"✅ 视频转码完成: {transcoded_path}")
        # 使用转码后的视频路径作为最终结果
        final_video_path = transcoded_path
    else:
        logger.warning("⚠️ 视频转码失败，使用原始视频")
        final_video_path = output_path

    # 生成视频的唯一标识
    video_id = os.path.splitext(os.path.basename(final_video_path))[0]

    # 存储检测数据（生产环境应使用数据库）
    video_detection_data[video_id] = {
        "detections": frame_detections,
        "video_info": {
            "width": w,
            "height": h,
            "fps": fps,
            "total_frames": total_frames,
            "processing_time": processing_time,
            "total_tracks": len(track_id_to_display_id),
            "transcoded": transcode_success,
            "original_path": output_path,
            "final_path": final_video_path
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
        "transcoded": transcode_success,
        "final_video_path": final_video_path,
        "detection_data": {
            "total_detections": sum(len(f["detections"]) for f in frame_detections),
            "unique_objects": len(track_id_to_display_id)
        }
    }


@router.post("/detect/video")
async def detect_video(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        conf: float = 0.5
):
    """
    支持框控制的视频检测接口，包含自动转码
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
    os.makedirs(TRANSCODED_DIR, exist_ok=True)

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
            logger.info("🔧🔧 开始视频处理任务...")

            # 处理视频
            result_info = process_video_with_controls(save_path, out_path, conf=conf)
            video_id = result_info["video_id"]
            final_video_path = result_info["final_video_path"]

            # 保存到数据库
            db = SessionLocal()
            try:
                record = DetectRecord(
                    type="video",
                    filename=save_name,
                    source_path=save_path,
                    result_path=final_video_path,  # 使用最终视频路径（可能是转码后的）
                    objects=json.dumps({
                        "video_id": video_id,
                        "total_tracks": result_info["total_tracks"],
                        "processing_time": result_info["processing_time"],
                        "transcoded": result_info["transcoded"],
                        "original_path": out_path,
                        "final_path": final_video_path
                    })
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                logger.info(f"💾💾 数据库记录已保存，记录ID: {record.id}")
            except Exception as db_error:
                logger.error(f"❌❌ 数据库保存失败: {db_error}")
                db.rollback()
            finally:
                db.close()

            logger.info(f"✅ 视频处理完成: {final_video_path}")

        except Exception as e:
            logger.error(f"❌❌ 处理视频时出错: {e}")
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
        "result_url": f"/api/files/result/{os.path.basename(out_path)}",
        "message": "视频正在处理中，处理完成后将自动转码优化",
        "features": {
            "box_controls": True,
            "realtime_toggle": True,
            "auto_transcode": True,
            "confidence_threshold": conf
        }
    }


@router.get("/video/transcode/status/{video_id}")
async def get_transcode_status(video_id: str):
    """
    获取视频转码状态
    """
    if video_id not in video_detection_data:
        raise HTTPException(status_code=404, detail="视频不存在")

    video_info = video_detection_data[video_id]["video_info"]

    return {
        "video_id": video_id,
        "transcoded": video_info.get("transcoded", False),
        "final_path": video_info.get("final_path", ""),
        "file_exists": os.path.exists(video_info.get("final_path", "")),
        "file_size": os.path.getsize(video_info.get("final_path", "")) if os.path.exists(
            video_info.get("final_path", "")) else 0
    }


@router.get("/video/play/{record_id}")
async def play_video(record_id: int):
    """播放视频文件（支持转码视频）"""
    db = SessionLocal()
    try:
        record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        # 确定视频文件路径
        video_path = None

        # 1. 首先检查记录中的结果路径
        if record.result_path and os.path.exists(record.result_path):
            video_path = record.result_path
            logger.info(f"🎬 使用结果路径: {video_path}")
        else:
            # 2. 检查转码目录
            if record.result_path:
                filename = os.path.basename(record.result_path)
                transcoded_path = os.path.join(TRANSCODED_DIR, f"transcoded_{filename}")
                if os.path.exists(transcoded_path):
                    video_path = transcoded_path
                    logger.info(f"🎬 使用转码路径: {video_path}")

            # 3. 如果还没有找到，尝试源文件
            if not video_path and record.source_path and os.path.exists(record.source_path):
                video_path = record.source_path
                logger.info(f"🎬 使用源文件路径: {video_path}")

        if not video_path or not os.path.exists(video_path):
            logger.error(f"❌ 视频文件不存在: {video_path}")
            raise HTTPException(status_code=404, detail="视频文件不存在")

        # 设置正确的MIME类型
        file_extension = os.path.splitext(video_path)[1].lower()
        media_type = "video/mp4" if file_extension == ".mp4" else "video/mp4"  # 默认为mp4

        # 返回视频流
        return FileResponse(
            video_path,
            media_type=media_type,
            filename=os.path.basename(video_path)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 播放视频失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"播放失败: {str(e)}")
    finally:
        db.close()
# 其他函数保持不变（draw_detection_box, draw_frame_stats等）
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

    # 其他路由函数保持不变...

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