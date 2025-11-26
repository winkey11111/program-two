# backend/routers/camera.py
from fastapi import APIRouter, Response, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import cv2, time, os, io, base64, aiofiles
from config import CAMERA_DIR, RESULT_DIR, MODEL_PATH
from ultralytics import YOLO
from db import SessionLocal
from models import DetectRecord
import numpy as np
import asyncio
import threading

router = APIRouter()
model = YOLO(MODEL_PATH)

# Simple MJPEG stream using server-side webcam capture.
# WARNING: This method opens the server's camera device (cv2.VideoCapture(0)).
# In containerized or remote servers this may not be available. For browser webcam,
# prefer frontend capture and send frames to backend (see /camera/frame below).

def gen_frames(conf=0.25):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # yield a minimal stream frame indicating error
        while True:
            time.sleep(1)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + b"" + b"\r\n")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            results = model.predict(source=frame, imgsz=960, conf=conf, save=False, verbose=False)
            r = results[0]
            if r.boxes is not None and len(r.boxes) > 0:
                for box, confs_i, cls_i in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
                    x1,y1,x2,y2 = map(int, box)
                    label = model.names[int(cls_i)]
                    cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
                    cv2.putText(frame, f"{label} {confs_i:.2f}", (x1, max(15,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
            ret2, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.03)
    finally:
        cap.release()

@router.get("/camera/stream")
def stream_camera():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# POST a snapshot frame from browser: front-end captures canvas and sends file
@router.post("/camera/frame")
async def camera_frame(file: UploadFile = File(...), conf: float = 0.25):
    timestamp = int(time.time()*1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(CAMERA_DIR, save_name)
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)
    # run detection similar to detect_image
    import cv2
    frame = cv2.imdecode(np.frombuffer(open(save_path,'rb').read(), np.uint8), cv2.IMREAD_COLOR)
    results = model.predict(source=frame, imgsz=960, conf=conf, save=False, verbose=False)
    r = results[0]
    detections = []
    if r.boxes is not None and len(r.boxes) > 0:
        img = frame.copy()
        for box, confs_i, cls_i in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            x1,y1,x2,y2 = map(int, box)
            label = model.names[int(cls_i)]
            detections.append({"class":label, "conf": float(confs_i), "bbox":[x1,y1,x2,y2]})
            cv2.rectangle(img, (x1,y1), (x2,y2), (0,255,0), 2)
            cv2.putText(img, f"{label} {confs_i:.2f}", (x1, max(15,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        out_name = f"res_{save_name}"
        out_path = os.path.join(RESULT_DIR, out_name)
        cv2.imwrite(out_path, img)
    else:
        out_name = f"res_{save_name}"
        out_path = os.path.join(RESULT_DIR, out_name)
        cv2.imwrite(out_path, frame)

    db = SessionLocal()
    record = DetectRecord(type="camera", filename=save_name, source_path=save_path, result_path=out_path, objects=detections)
    db.add(record)
    db.commit()
    db.refresh(record)
    db.close()

    return {"id": record.id, "result_url": f"/api/files/result/{os.path.basename(out_path)}", "objects": detections}

# POST an uploaded recorded clip from browser
@router.post("/camera/save")
async def camera_save(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".mp4", ".webm", ".mov", ".mkv", ".avi"]:
        raise HTTPException(status_code=400, detail="unsupported format")
    timestamp = int(time.time()*1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(CAMERA_DIR, save_name)
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # optional: process to draw boxes per frame (reuse video.process)
    # For now, save original and write DB record
    db = SessionLocal()
    record = DetectRecord(type="camera_video", filename=save_name, source_path=save_path, result_path=save_path, objects=[])
    db.add(record)
    db.commit()
    db.refresh(record)
    db.close()
    return {"id": record.id, "source_path": save_path}
