from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
import cv2, time, os, aiofiles
from config import CAMERA_DIR, RESULT_DIR, MODEL_PATH
from ultralytics import YOLO
from db import SessionLocal
from models import DetectRecord
import numpy as np
import threading

router = APIRouter()
model = YOLO(MODEL_PATH)

# -----------------------------
# 全局变量
# -----------------------------
latest_frame = None
latest_detections = []
stop_camera = False
camera_started = False

# -----------------------------
# 摄像头读取线程
# -----------------------------
def camera_reader():
    global latest_frame, stop_camera
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    while not stop_camera:
        ret, frame = cap.read()
        if ret:
            latest_frame = frame
        time.sleep(0.001)
    cap.release()

# -----------------------------
# YOLO 异步推理线程
# -----------------------------
def yolo_worker(conf=0.25):
    global latest_frame, latest_detections, stop_camera
    frame_count = 0

    while not stop_camera:
        if latest_frame is None:
            time.sleep(0.01)
            continue

        frame_count += 1
        # 每隔2帧做一次推理
        if frame_count % 2 != 0:
            time.sleep(0.01)
            continue

        frame = latest_frame.copy()
        results = model.predict(frame, imgsz=416, conf=conf, save=False, verbose=False)
        r = results[0]

        new_detections = []
        if r.boxes is not None and len(r.boxes) > 0:
            for box, conf_i, cls_i in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
                new_detections.append({
                    "class": model.names[int(cls_i)],
                    "conf": float(conf_i),
                    "bbox": list(map(int, box))
                })
        latest_detections[:] = new_detections  # 更新检测结果

# -----------------------------
# MJPEG 推流生成器
# -----------------------------
def gen_frames():
    global latest_frame, latest_detections
    while True:
        if latest_frame is None:
            time.sleep(0.01)
            continue

        frame = latest_frame.copy()

        # 绘制最新检测框
        for det in latest_detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["class"]
            conf = det["conf"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame_bytes +
            b"\r\n"
        )
        time.sleep(0.01)

# -----------------------------
# 摄像头流接口
# -----------------------------
@router.get("/camera/stream")
def stream_camera():
    global camera_started
    if not camera_started:
        camera_started = True
        threading.Thread(target=camera_reader, daemon=True).start()
        threading.Thread(target=yolo_worker, daemon=True).start()

    return StreamingResponse(
        gen_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# -----------------------------
# 单帧抓拍模式（保持原样）
# -----------------------------
@router.post("/camera/frame")
async def camera_frame(file: UploadFile = File(...), conf: float = 0.25):
    timestamp = int(time.time() * 1000)
    save_name = f"{timestamp}_{file.filename}"
    save_path = os.path.join(CAMERA_DIR, save_name)

    async with aiofiles.open(save_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    frame = cv2.imdecode(np.frombuffer(open(save_path, 'rb').read(), np.uint8), cv2.IMREAD_COLOR)

    results = model.predict(frame, imgsz=960, conf=conf, save=False, verbose=False)
    r = results[0]

    detections = []
    img = frame.copy()

    if r.boxes is not None and len(r.boxes) > 0:
        for box, conf_i, cls_i in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls_i)]
            detections.append({"class": label, "conf": float(conf_i), "bbox": [x1, y1, x2, y2]})
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{label} {conf_i:.2f}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    out_name = f"res_{save_name}"
    out_path = os.path.join(RESULT_DIR, out_name)
    cv2.imwrite(out_path, img)

    db = SessionLocal()
    record = DetectRecord(
        type="camera",
        filename=save_name,
        source_path=save_path,
        result_path=out_path,
        objects=detections
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    db.close()

    return {
        "id": record.id,
        "result_url": f"/api/files/result/{os.path.basename(out_path)}",
        "objects": detections
    }
