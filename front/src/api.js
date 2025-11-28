import axios from "axios";

// API 基础地址，默认为本地开发地址
const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

/**
 * 上传图片进行目标检测
 * @param {File} file - 用户选择的图片文件
 * @returns {Promise<Object>} 检测结果数据
 */
export async function uploadImage(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/detect/image`, f, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

/**
 * 上传视频进行目标追踪
 * @param {File} file - 用户选择的视频文件
 * @returns {Promise<Object>} 追踪结果数据（如任务ID、状态等）
 */
export async function uploadVideo(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/detect/video`, f, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

/**
 * 获取识别历史记录列表
 * @param {number} limit - 最大返回条数，默认50
 * @param {string|null} type - 筛选类型（如 'image', 'video', 'camera'），可选
 * @returns {Promise<Array>} 历史记录数组
 */
export async function getRecords(limit = 50, type = null) {
  let url = `${BASE}/records/list?limit=${limit}`;
  if (type) url += `&type=${type}`;
  const r = await axios.get(url);
  return r.data;
}
export async function getRecordsPaged(page = 1, limit = 20, type = null) {
  const params = { page, limit };
  if (type) params.type = type;
  const r = await axios.get(`${BASE}/records/list`, { params });
  return {
    total: r.data.total,
    data: r.data.data
  };
}

/**
 * 删除指定ID的历史记录（包括原始文件和结果文件）
 * @param {number|string} id - 记录ID
 * @returns {Promise<Object>} 删除操作的响应数据
 */
export async function deleteRecord(id) {
  const r = await axios.delete(`${BASE}/records/${id}`);
  return r.data;
}

/**
 * 上传摄像头单帧图像进行实时检测
 * @param {Blob} blob - 摄像头捕获的图像 Blob
 * @param {string} filename - 文件名，默认为 'frame.jpg'
 * @returns {Promise<Object>} 实时检测结果
 */
export async function postCameraFrame(blob, filename = "frame.jpg") {
  const f = new FormData();
  f.append("file", blob, filename);
  const r = await axios.post(`${BASE}/camera/frame`, f, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

/**
 * 保存摄像头录制的视频片段
 * @param {File} file - 录制的视频文件
 * @returns {Promise<Object>} 保存结果（如记录ID）
 */
export async function saveCameraClip(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/camera/save`, f, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}