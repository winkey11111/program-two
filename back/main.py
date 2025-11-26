from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import detect, video, camera, records
import uvicorn

app = FastAPI(title="YOLOv8 Detection & Tracking")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产调整
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect.router, prefix="/api")
app.include_router(video.router, prefix="/api")
app.include_router(camera.router, prefix="/api")
app.include_router(records.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
