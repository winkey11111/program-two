CREATE DATABASE IF NOT EXISTS yolo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE yolo_db;

CREATE TABLE IF NOT EXISTS detect_record (
  id INT AUTO_INCREMENT PRIMARY KEY,
  type VARCHAR(20),
  filename VARCHAR(255),
  source_path VARCHAR(512),
  result_path VARCHAR(512),
  objects JSON,
  detect_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
