# backend/routers/video.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
import os, time, aiofiles, shutil
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord
from ultralytics import YOLO
import cv2

router = APIRouter()
# use a separate model instance for tracking/video processing
model = YOLO(MODEL_PATH)

def process_video(input_path: str, output_path: str, conf: float = 0.25):
    """
    Use ultralytics track to process video (includes tracker param).
    This will save a tracked video with IDs drawn.
    """
    # ultralytics .track method will write to runs/track/exp by default.
    # Simpler: process frames and write output ourselves using model.predict on frames and drawing boxes.
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (w,h))
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results = model.predict(source=frame, imgsz=1280, conf=conf, save=False, verbose=False)
        r = results[0]
        if r.boxes is not None and len(r.boxes) > 0:
            for box, confs_i, cls_i in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
                x1,y1,x2,y2 = map(int, box)
                label = model.names[int(cls_i)]
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(frame, f"{label} {confs_i:.2f}", (x1, max(15,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        out.write(frame)
    cap.release()
    out.release()

@router.post("/detect/video")
async def detect_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = None, conf: float = 0.25):
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".mp4", ".avi", ".mov", ".mkv"]:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    timestamp = int(time.time()*1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    out_name = f"res_{save_name}.mp4"
    out_path = os.path.join(RESULT_DIR, out_name)

    def _bg_task():
        process_video(save_path, out_path, conf=conf)
        # write to DB
        db = SessionLocal()
        record = DetectRecord(type="video", filename=save_name, source_path=save_path, result_path=out_path, objects=[])
        db.add(record)
        db.commit()
        db.close()

    if background_tasks:
        background_tasks.add_task(_bg_task)

    # immediate response says processing; final video at result url when done
    return {"status":"processing", "result_url": f"/api/files/result/{out_name}"}
