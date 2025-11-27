# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
import os, time, aiofiles, shutil
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord
from ultralytics import YOLO
import cv2
import numpy as np
from collections import defaultdict, deque
import scipy.spatial as spatial

router = APIRouter()
model = YOLO(MODEL_PATH)


def process_video_stable(input_path: str, output_path: str, conf: float = 0.6):
    """
    改进的稳定跟踪版本，解决静态画面ID跳变问题
    """
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w, h = int(cap.get(3)), int(cap.get(4))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    # 更严格的跟踪参数，提高稳定性
    results = model.track(
        source=input_path,
        imgsz=1280,
        conf=conf,
        iou=0.7,  # 提高IOU阈值
        persist=True,
        tracker="bytetrack.yaml",
        verbose=False,
        stream=True,
        classes=[0, 2]  # 可选：只跟踪人和车，减少干扰
    )

    # 跟踪状态管理
    active_tracks = {}  # 当前活跃轨迹: {track_id: TrackInfo}
    next_display_id = 1  # 显示ID计数器
    track_id_to_display_id = {}  # 映射关系
    frame_history = deque(maxlen=10)  # 保存最近帧的跟踪结果

    class TrackInfo:
        def __init__(self, track_id, class_name, bbox, display_id):
            self.track_id = track_id
            self.class_name = class_name
            self.bbox = bbox  # [x1, y1, x2, y2]
            self.display_id = display_id
            self.stable_frames = 0  # 稳定帧数计数器
            self.last_seen = 0  # 最后出现的帧号

    for frame_idx, result in enumerate(results):
        frame = result.orig_img.copy()

        if result.boxes is not None and result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            track_ids = result.boxes.id.cpu().numpy().astype(int)
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)

            # 按置信度排序并过滤
            indices = np.argsort(confidences)[::-1]
            current_frame_tracks = {}

            for i in indices:
                if confidences[i] < conf * 0.8:  # 额外过滤低置信度
                    continue

                box = boxes[i]
                track_id = track_ids[i]
                class_id = class_ids[i]
                class_name = model.names[int(class_id)]

                x1, y1, x2, y2 = map(int, box)
                area = (x2 - x1) * (y2 - y1)

                # 过滤过小目标
                if area < 300:
                    continue

                # 检查是否为已有轨迹
                if track_id in active_tracks:
                    track_info = active_tracks[track_id]
                    # 计算与上一帧的位置变化
                    prev_bbox = track_info.bbox
                    center_prev = [(prev_bbox[0] + prev_bbox[2]) / 2, (prev_bbox[1] + prev_bbox[3]) / 2]
                    center_curr = [(x1 + x2) / 2, (y1 + y2) / 2]
                    movement = np.sqrt((center_curr[0] - center_prev[0]) ** 2 +
                                       (center_curr[1] - center_prev[1]) ** 2)

                    # 如果移动很小，增加稳定计数
                    if movement < 5:  # 移动小于5像素认为基本静止
                        track_info.stable_frames += 1
                    else:
                        track_info.stable_frames = max(0, track_info.stable_frames - 1)

                    # 更新轨迹信息
                    track_info.bbox = [x1, y1, x2, y2]
                    track_info.last_seen = frame_idx

                else:
                    # 新轨迹：检查是否可能是已有轨迹的ID跳变
                    matched_existing = False
                    for existing_id, existing_track in list(active_tracks.items()):
                        if existing_track.last_seen < frame_idx - 5:  # 超过5帧未出现
                            continue

                        # 计算与已有轨迹的位置相似度
                        existing_bbox = existing_track.bbox
                        center_existing = [(existing_bbox[0] + existing_bbox[2]) / 2,
                                           (existing_bbox[1] + existing_bbox[3]) / 2]
                        center_new = [(x1 + x2) / 2, (y1 + y2) / 2]
                        distance = np.sqrt((center_new[0] - center_existing[0]) ** 2 +
                                           (center_new[1] - center_existing[1]) ** 2)

                        # 如果位置接近且类别相同，认为是同一目标
                        if distance < 50 and existing_track.class_name == class_name:
                            # 重用原有的显示ID
                            display_id = existing_track.display_id
                            track_id_to_display_id[track_id] = display_id
                            # 移除旧轨迹
                            del active_tracks[existing_id]
                            # 创建新轨迹但重用显示ID
                            track_info = TrackInfo(track_id, class_name, [x1, y1, x2, y2], display_id)
                            track_info.stable_frames = existing_track.stable_frames
                            active_tracks[track_id] = track_info
                            matched_existing = True
                            break

                    if not matched_existing:
                        # 真正的新目标
                        display_id = next_display_id
                        next_display_id += 1
                        track_id_to_display_id[track_id] = display_id
                        track_info = TrackInfo(track_id, class_name, [x1, y1, x2, y2], display_id)
                        active_tracks[track_id] = track_info

                current_frame_tracks[track_id] = active_tracks[track_id]

            # 清理长时间未出现的轨迹
            for track_id in list(active_tracks.keys()):
                if active_tracks[track_id].last_seen < frame_idx - 30:  # 30帧未出现
                    del active_tracks[track_id]
                    if track_id in track_id_to_display_id:
                        # 可选：回收显示ID，但可能造成混淆
                        # 这里选择不回收，保持ID唯一性
                        pass

            # 绘制当前帧的跟踪结果
            for track_id, track_info in current_frame_tracks.items():
                x1, y1, x2, y2 = track_info.bbox
                class_name = track_info.class_name
                display_id = track_info.display_id

                # 根据稳定性选择颜色：越稳定颜色越深
                stability = min(track_info.stable_frames / 10.0, 1.0)
                if stability > 0.7:  # 高度稳定
                    color = (0, 200, 0)  # 深绿色
                elif stability > 0.3:  # 中等稳定
                    color = (0, 255, 255)  # 黄色
                else:  # 不稳定
                    color = (0, 0, 255)  # 红色

                # 绘制边界框
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # 绘制标签（显示稳定度）
                label = f"{class_name[0].upper()}{display_id}"
                if track_info.stable_frames < 5:  # 不稳定时显示警告
                    label += "?"

                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

                # 标签背景
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                              (x1 + label_size[0] + 10, y1), color, -1)

                # 标签文字
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10),
                              (x1 + label_size[0] + 10, y1), color, 2)

                cv2.putText(frame, label, (x1 + 5, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # 添加统计信息
        stable_count = sum(1 for t in active_tracks.values() if t.stable_frames > 5)
        stats_text = f"Frame: {frame_idx} | Tracks: {len(active_tracks)} | Stable: {stable_count}"
        cv2.putText(frame, stats_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(frame, stats_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        out.write(frame)

        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx} frames, active tracks: {len(active_tracks)}")

    cap.release()
    out.release()
    print(f"Video processing completed. Total display IDs used: {next_display_id}")


@router.post("/detect/video")
async def detect_video(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        conf: float = 0.6
):
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="Unsupported video format")

    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    out_name = f"res_{save_name}.mp4"
    out_path = os.path.join(RESULT_DIR, out_name)

    def _bg_task():
        try:
            process_video_stable(save_path, out_path, conf=conf)
            db = SessionLocal()
            record = DetectRecord(
                type="video",
                filename=save_name,
                source_path=save_path,
                result_path=out_path,
                objects=[]
            )
            db.add(record)
            db.commit()
            db.close()
            print(f"Stable video processing completed: {out_path}")
        except Exception as e:
            print(f"Error processing video: {e}")

    if background_tasks:
        background_tasks.add_task(_bg_task)

    return {
        "status": "processing",
        "result_url": f"/api/files/result/{out_name}",
        "message": "使用稳定跟踪算法，解决静态画面ID跳变问题",
        "config": {
            "confidence_threshold": conf,
            "stable_tracking": True
        }
    }