import os
from urllib.parse import quote_plus

# -------------------------------
# 基础目录和文件路径
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
RESULT_DIR = os.path.join(BASE_DIR, "static", "results")
CAMERA_DIR = os.path.join(BASE_DIR, "static", "camera_records")
MODEL_PATH = os.path.join(BASE_DIR, "yolov8", "best.pt")

# 自动创建目录（如果不存在）
for directory in [UPLOAD_DIR, RESULT_DIR, CAMERA_DIR]:
    os.makedirs(directory, exist_ok=True)

# -------------------------------
# 数据库配置（改为 SQLite）
# -------------------------------
# SQLite 数据库存放路径：与项目同级的 db 目录下
DB_DIR = os.path.join(BASE_DIR, "db")
os.makedirs(DB_DIR, exist_ok=True)  # 确保 db 目录存在

DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'example.db')}"