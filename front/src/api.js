import axios from "axios";

// API 基础地址，默认为本地开发地址
//const BASE = import.meta.env.VITE_API_BASE || "http://192.168.8.101:8000/api";
const BASE = import.meta.env.VITE_API_BASE || "https://nonintellectually-subsonic-kai.ngrok-free.dev/api";
const FILE_BASE = BASE.replace("/api", ""); // 自动从BASE中移除/api

/**
 * 上传图片进行目标检测
 */
export async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post(`${BASE}/detect/image`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

/**
 * 上传视频进行目标追踪（带置信度）
 */
export async function uploadVideo(file, conf = 0.5) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("conf", conf.toString());
  const res = await axios.post(`${BASE}/detect/video`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

/**
 * 分页获取记录列表（推荐使用）
 */
export async function getRecordsPaged(page = 1, limit = 20, type = null) {
  const params = { page, limit };
  if (type) params.type = type;
  const res = await axios.get(`${BASE}/records/list`, { params });
  return {
    total: res.data.total,
    data: res.data.data,
  };
}

/**
 * 获取单条记录详情（含 source_url 和 result_url）
 */
export async function getRecord(id) {
  const res = await axios.get(`${BASE}/records/${id}`);
  return res.data;
}

/**
 * 删除指定ID的历史记录（可选是否删除物理文件）
 */
export async function deleteRecord(id, deleteFiles = false) {
  const params = deleteFiles ? { delete_files: "true" } : {};
  const res = await axios.delete(`${BASE}/records/${id}`, { params });
  return res.data;
}

// ========== 视频专用控制 API ==========

/**
 * 切换视频中检测框的显示状态（支持隐藏多个 ID）
 * 注意：hiddenIds 是 number[]，但 FastAPI Query 默认接收字符串，需用 params 传递
 */
export async function toggleVideoBoxes(videoId, hiddenIds, regenerate = false) {
  // 使用 URLSearchParams 自动处理数组转字符串
  const params = new URLSearchParams();
  hiddenIds.forEach(id => params.append('hidden_ids', id.toString()));
  params.append('regenerate', regenerate.toString());

  const res = await axios.post(`${BASE}/video/${videoId}/toggle-boxes`, null, {
    params,
    headers: { "Content-Type": "application/json" }
  });
  return res.data;
}

/**
 * 获取视频检测数据（整段摘要 或 单帧详情）
 */
export async function getVideoDetections(videoId, frameIndex = null) {
  const params = frameIndex !== null ? { frame_index: frameIndex } : {};
  const res = await axios.get(`${BASE}/video/${videoId}/detections`, { params });
  return res.data;
}

/**
 * 获取视频中所有出现的物体对象列表（按 track ID 聚合）
 */
export async function getVideoObjects(videoId) {
  const res = await axios.get(`${BASE}/video/${videoId}/objects`);
  return res.data;
}

/**
 * 重置视频框显示（全部可见）
 */
export async function resetVideoBoxes(videoId) {
  const res = await axios.post(`${BASE}/video/${videoId}/reset`);
  return res.data;
}

/**
 * 构造结果视频的直接访问 URL（用于 <video> 标签）
 */
export function getVideoResultUrl(filename) {
  return `${FILE_BASE}/files/result/${encodeURIComponent(filename)}`;
}

/**
 * 构造原始视频的直接访问 URL
 */
export function getVideoSourceUrl(filename) {
  return `${FILE_BASE}/files/upload/${encodeURIComponent(filename)}`;
}

// ========== 摄像头相关 API ==========

export async function postCameraFrame(blob, filename = "frame.jpg") {
  const formData = new FormData();
  formData.append("file", blob, filename);
  const res = await axios.post(`${BASE}/camera/frame`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function saveCameraClip(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post(`${BASE}/camera/save`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function startCameraDetection(config = {}) {
  const res = await axios.post(`${BASE}/camera/start`, config);
  return res.data;
}

export async function stopCameraDetection() {
  const res = await axios.post(`${BASE}/camera/stop`);
  return res.data;
}

export async function getCameraStatus() {
  const res = await axios.get(`${BASE}/camera/status`);
  return res.data;
}

export async function getCameraList() {
  const res = await axios.get(`${BASE}/camera/list`);
  return res.data;
}
//===========图片相关API=============
/**
 * 构造图片结果的直接访问URL
 */
export function getImageResultUrl(filename) {
  return `${FILE_BASE}/files/result/${encodeURIComponent(filename)}`;
}

/**
 * 构造原始图片的直接访问URL
 */
export function getImageSourceUrl(filename) {
  return `${FILE_BASE}/files/upload/${encodeURIComponent(filename)}`;
}

// ========== 模型管理 API ==========

export async function getModelInfo() {
  const res = await axios.get(`${BASE}/model/info`);
  return res.data;
}

export async function switchModel(modelPath) {
  const res = await axios.post(`${BASE}/model/switch`, { model_path: modelPath });
  return res.data;
}

export async function getModelList() {
  const res = await axios.get(`${BASE}/model/list`);
  return res.data;
}

// ========== 系统状态 API ==========

export async function getSystemStatus() {
  const res = await axios.get(`${BASE}/system/status`);
  return res.data;
}

export async function getGPUStatus() {
  const res = await axios.get(`${BASE}/system/gpu`);
  return res.data;
}

export async function getMemoryStatus() {
  const res = await axios.get(`${BASE}/system/memory`);
  return res.data;
}

export async function getCPUStatus() {
  const res = await axios.get(`${BASE}/system/cpu`);
  return res.data;
}

/**
 * 获取视频处理状态
 */
export async function getVideoStatus(videoId) {
  const res = await axios.get(`${BASE}/video/${videoId}/status`);
  return res.data; // 应返回 { status: 'processing' | 'completed', progress?: number }
}