from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import detect, video, camera, records
import uvicorn
import os
from pathlib import Path

# 获取项目根目录：假设 main.py 在 program/back/ 下，则根目录是 program/
BASE_DIR = Path(__file__).resolve().parent

# 正确指向 static 目录下的 uploads 和 results
UPLOAD_DIR = (BASE_DIR / "static" / "uploads").as_posix()
RESULT_DIR = (BASE_DIR / "static" / "results").as_posix()

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

app = FastAPI(title="YOLOv8 Detection & Tracking")

# 挂载静态文件服务
app.mount("/files/upload", StaticFiles(directory=UPLOAD_DIR), name="upload")
app.mount("/files/result", StaticFiles(directory=RESULT_DIR), name="result")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(detect.router, prefix="/api")
app.include_router(video.router, prefix="/api")
app.include_router(camera.router, prefix="/api")
app.include_router(records.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
