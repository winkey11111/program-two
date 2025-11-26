# backend/routers/detect.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os, time, shutil, aiofiles, json
from config import UPLOAD_DIR, RESULT_DIR, MODEL_PATH
from db import SessionLocal
from models import DetectRecord, Base
from ultralytics import YOLO
import cv2
import numpy as np

router = APIRouter()
model = YOLO(MODEL_PATH)

# Ensure tables
def init_db():
    from db import engine
    Base.metadata.create_all(bind=engine)
init_db()

@router.post("/detect/image")
async def detect_image(file: UploadFile = File(...), conf: float = 0.25):
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".bmp"]:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    timestamp = int(time.time()*1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # run inference
    results = model.predict(source=save_path, imgsz=1280, conf=conf, save=False, verbose=False)
    r = results[0]
    img = cv2.imread(save_path)
    detections = []
    if r.boxes is not None and len(r.boxes) > 0:
        boxes = r.boxes.xyxy.tolist()
        confs = r.boxes.conf.tolist()
        cls_ids = r.boxes.cls.tolist()
        for box, confs_i, cls_i in zip(boxes, confs, cls_ids):
            x1,y1,x2,y2 = map(int, box)
            label = model.names[int(cls_i)]
            detections.append({
                "class": label,
                "conf": float(confs_i),
                "bbox": [x1,y1,x2,y2]
            })
            cv2.rectangle(img, (x1,y1), (x2,y2), (0,255,0), 2)
            cv2.putText(img, f"{label} {confs_i:.2f}", (x1, max(15,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    out_name = f"res_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    # write db
    db = SessionLocal()
    record = DetectRecord(type="image", filename=save_name, source_path=save_path, result_path=out_path, objects=detections)
    db.add(record)
    db.commit()
    db.refresh(record)
    db.close()

    return {"id": record.id, "result_url": f"/api/files/result/{out_name}", "objects": detections}

@router.get("/files/result/{filename}")
def get_result_file(filename: str):
    p = os.path.join(RESULT_DIR, filename)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)
