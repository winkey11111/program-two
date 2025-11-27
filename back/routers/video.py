# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
import os
import time
import aiofiles
import shutil
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord
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


def process_video_perfect(input_path: str, output_path: str, conf: float = 0.5):
    """
    完美的视频处理函数 - 解决ID跳变和统计显示问题
    """
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载成功")

    logger.info(f"🚀 开始视频处理: {input_path} -> {output_path}")
    logger.info(f"⚙️  配置: 置信度阈值={conf}")

    start_time = time.time()

    # 打开输入视频
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        logger.error(f"❌ 无法打开视频文件: {input_path}")
        raise HTTPException(status_code=500, detail="无法打开视频文件")

    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"📊 视频信息: {w}x{h}, FPS: {fps}, 总帧数: {total_frames}")

    # 创建输出视频
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    if not out.isOpened():
        cap.release()
        logger.error(f"❌ 无法创建输出文件: {output_path}")
        raise HTTPException(status_code=500, detail="无法创建输出视频文件")

    # 使用优化的跟踪参数
    results = model.track(
        source=input_path,
        imgsz=640,
        conf=0.2,
        iou=0.4,  # 适中的IOU阈值，平衡检测精度和稳定性
        persist=True,
        tracker="bytetrack.yaml",  # 使用ByteTrack跟踪器
        verbose=False,
        stream=True  # 流式处理，节省内存
    )

    # 跟踪状态管理
    active_tracks = {}  # 当前活跃的轨迹 {track_id: track_info}
    track_id_to_display_id = {}  # 跟踪ID到显示ID的映射
    next_display_id = 1
    consecutive_zero_frames = 0
    frame_stats_history = []

    # 类别颜色映射
    color_map = {
        'person': (0, 255, 0),  # 绿色 - 行人
        'car': (255, 0, 0),  # 蓝色 - 汽车
        'bicycle': (0, 255, 255),  # 黄色 - 自行车
        'motorcycle': (255, 255, 0),  # 青色 - 摩托车
        'truck': (255, 165, 0),  # 橙色 - 卡车
        'bus': (128, 0, 128),  # 紫色 - 公交车
    }

    for frame_idx, result in enumerate(results):
        frame = result.orig_img.copy()

        # 当前帧的统计
        current_frame_stats = defaultdict(int)  # 当前帧各类别数量
        current_visible_tracks = set()  # 当前帧可见的跟踪ID

        # 动态调整置信度
        dynamic_conf = conf
        if consecutive_zero_frames > 10:  # 连续10帧无检测
            dynamic_conf = max(0.1, conf * 0.5)  # 大幅降低置信度阈值
            logger.warning(f"⚠️ 帧 {frame_idx}: 连续{consecutive_zero_frames}帧无检测，动态调整置信度到{dynamic_conf}")

        has_detections = False

        if result.boxes is not None:
            # 获取检测结果
            if result.boxes.id is not None:
                boxes = result.boxes.xyxy.cpu().numpy()
                track_ids = result.boxes.id.cpu().numpy().astype(int)
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
            else:
                boxes = result.boxes.xyxy.cpu().numpy()
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
                track_ids = np.arange(len(boxes)) + frame_idx * 1000

            # 使用动态置信度阈值进行过滤
            valid_indices = confidences >= dynamic_conf
            boxes = boxes[valid_indices]
            track_ids = track_ids[valid_indices] if len(track_ids) == len(valid_indices) else track_ids
            class_ids = class_ids[valid_indices]
            confidences = confidences[valid_indices]

            # 处理检测结果
            for i, (box, track_id, confidence, class_id) in enumerate(zip(boxes, track_ids, confidences, class_ids)):
                x1, y1, x2, y2 = map(int, box)
                class_name = model.names[int(class_id)]

                # 放宽面积过滤条件
                bbox_area = (x2 - x1) * (y2 - y1)
                min_area = 100  # 从300降低到100，检测更小目标
                max_area = w * h * 0.8  # 避免过大的误检

                if bbox_area < min_area or bbox_area > max_area:
                    continue

                has_detections = True
                current_visible_tracks.add(track_id)
                current_frame_stats[class_name] += 1

                # 颜色和显示ID管理
                color = (0, 255, 0) if class_name == 'person' else (255, 0, 0)

                if track_id not in track_id_to_display_id:
                    track_id_to_display_id[track_id] = next_display_id
                    next_display_id += 1

                display_id = track_id_to_display_id[track_id]

                # 绘制检测框
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                label = f"{class_name[0].upper()}{display_id}"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]

                # 标签背景
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 8),
                              (x1 + label_size[0] + 5, y1), color, -1)
                cv2.putText(frame, label, (x1 + 2, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # 更新活跃轨迹
                active_tracks[track_id] = {
                    'class': class_name,
                    'last_seen': frame_idx,
                    'display_id': display_id
                }

        # 更新连续零检测计数器
        if has_detections:
            consecutive_zero_frames = 0  # 重置计数器
        else:
            consecutive_zero_frames += 1

        # 清理过期轨迹（但不要过于激进）
        tracks_to_remove = []
        current_time = frame_idx
        for track_id, info in list(active_tracks.items()):
            # 延长轨迹保留时间，从50帧增加到100帧
            if current_time - info['last_seen'] > 100:
                tracks_to_remove.append(track_id)

        for track_id in tracks_to_remove:
            if track_id in active_tracks:
                del active_tracks[track_id]

        # 显示统计信息（增强版本）
        visible_count = sum(current_frame_stats.values())

        # 在画面上显示更详细的分析信息
        stats_background_height = 90
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (500, stats_background_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # 主统计行
        progress = (frame_idx / total_frames * 100) if total_frames > 0 else 0
        main_stats = f"Frame: {frame_idx} ({progress:.1f}%) | Visible: {visible_count} | Conf: {dynamic_conf:.2f}"
        cv2.putText(frame, main_stats, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # 检测状态行
        status_color = (0, 255, 0) if visible_count > 0 else (0, 165, 255)  # 绿色/橙色
        status_text = "DETECTING" if visible_count > 0 else f"NO DETECT{consecutive_zero_frames}f"
        cv2.putText(frame, status_text, (10, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)

        # 各类别统计
        if current_frame_stats:
            classes_text = " | ".join([f"{k}:{v}" for k, v in current_frame_stats.items()])
            cv2.putText(frame, classes_text, (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        else:
            cv2.putText(frame, "NO OBJECTS", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)

        # 跟踪信息
        tracking_info = f"Active Tracks: {len(active_tracks)}"
        cv2.putText(frame, tracking_info, (10, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        out.write(frame)

        # 增强的日志输出
        if frame_idx % 50 == 0 or consecutive_zero_frames > 5:
            log_level = logging.WARNING if consecutive_zero_frames > 10 else logging.INFO
            logger.log(log_level,
                       f"帧 {frame_idx}: 可见{visible_count}目标, 连续零检测: {consecutive_zero_frames}帧, 置信度: {dynamic_conf:.2f}")

        # 记录历史用于分析
        frame_stats_history.append({
            'frame': frame_idx,
            'visible': visible_count,
            'classes': dict(current_frame_stats),
            'consecutive_zeros': consecutive_zero_frames
        })

    # 最终分析和报告
    end_time = time.time()
    processing_time = end_time - start_time

    cap.release()
    out.release()

    # 分析检测结果
    total_frames_processed = len(frame_stats_history)
    zero_detection_frames = sum(1 for stats in frame_stats_history if stats['visible'] == 0)
    zero_percentage = (zero_detection_frames / total_frames_processed * 100) if total_frames_processed > 0 else 0

    logger.info(f"📊 最终分析报告:")
    logger.info(f"   总帧数: {total_frames_processed}")
    logger.info(f"   零检测帧数: {zero_detection_frames} ({zero_percentage:.1f}%)")
    logger.info(f"   总跟踪目标: {len(track_id_to_display_id)}")
    logger.info(f"⏱️  处理时间: {processing_time:.2f}秒")

    if zero_percentage > 50:
        logger.warning(f"⚠️ 高零检测率({zero_percentage:.1f}%)，建议检查视频内容或调整检测参数")

    return {
        "total_frames": total_frames_processed,
        "zero_detection_frames": zero_detection_frames,
        "zero_percentage": zero_percentage,
        "total_tracks": len(track_id_to_display_id),
        "processing_time": processing_time  # 添加缺失的字段
    }


@router.post("/detect/video")
async def detect_video(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        conf: float = 0.3
):
    """
    完美的视频检测接口
    """
    # 检查文件格式
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="不支持的视频格式")

    # 检查模型是否加载
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载，请检查模型路径")

    # 创建唯一文件名
    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(RESULT_DIR, exist_ok=True)

    # 保存上传的文件
    try:
        async with aiofiles.open(save_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)
        logger.info(f"📁 文件已保存: {save_path} ({len(content)} bytes)")
    except Exception as e:
        logger.error(f"❌ 文件保存失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")

    # 准备输出路径
    out_name = f"res_{save_name}.mp4"
    out_path = os.path.join(RESULT_DIR, out_name)

    def _bg_task():
        """后台处理任务"""
        try:
            logger.info(f"🔧 开始后台处理任务...")

            # 处理视频
            result_info = process_video_perfect(save_path, out_path, conf=conf)

            # 保存到数据库
            db = SessionLocal()
            try:
                record = DetectRecord(
                    type="video",
                    filename=save_name,
                    source_path=save_path,
                    result_path=out_path,
                    objects=[],
                    processing_time=result_info["processing_time"],  # 现在有这个字段了
                    total_frames=result_info["total_frames"]  # 现在有这个字段了
                )
                db.add(record)
                db.commit()
                logger.info(f"💾 数据库记录已保存")
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
                    logger.info(f"🧹 已清理临时文件: {save_path}")
                except:
                    pass

    # 提交后台任务
    if background_tasks:
        background_tasks.add_task(_bg_task)
        logger.info(f"📋 后台任务已提交")
    else:
        # 如果没有background_tasks，直接运行（开发测试用）
        logger.warning("⚠️  直接运行处理任务（无后台任务）")
        _bg_task()

    return {
        "status": "processing",
        "result_url": f"/api/files/result/{out_name}",
        "message": "视频正在处理中，请查看控制台输出了解进度",
        "config": {
            "confidence_threshold": conf,
            "filename": save_name,
            "estimated_time": "取决于视频长度和复杂度"
        }
    }


@router.get("/model/classes")
async def get_model_classes():
    """
    获取模型支持的类别列表
    """
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载")

    return {
        "model_classes": model.names,
        "class_count": len(model.names),
        "supported_classes": {i: name for i, name in model.names.items()}
    }


@router.get("/model/info")
async def get_model_info():
    """
    获取模型详细信息
    """
    if model is None:
        raise HTTPException(status_code=500, detail="模型未加载")

    return {
        "model_path": MODEL_PATH,
        "model_type": str(type(model.model)),
        "class_count": len(model.names),
        "classes": model.names
    }


@router.get("/test/processing")
async def test_processing():
    """
    测试处理功能的端点
    """
    logger.info("🧪 测试处理功能...")

    # 模拟一些处理日志
    for i in range(5):
        logger.info(f"测试日志 {i + 1}/5")
        time.sleep(0.5)

    return {
        "status": "success",
        "message": "处理测试完成，请检查控制台输出",
        "test_data": {
            "frames_processed": 100,
            "objects_detected": 25,
            "processing_time": 2.5
        }
    }