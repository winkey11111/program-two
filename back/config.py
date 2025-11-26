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
# 数据库配置
# -------------------------------
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Wds030408@")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "yolo_db")

# 对密码进行 URL 编码，防止特殊字符导致连接失败
DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)

# SQLAlchemy 数据库 URL
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
