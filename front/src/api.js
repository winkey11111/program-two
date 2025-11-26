import axios from "axios";
const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export async function uploadImage(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/detect/image`, f, { headers: {"Content-Type": "multipart/form-data"}});
  return r.data;
}

export async function uploadVideo(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/detect/video`, f, { headers: {"Content-Type": "multipart/form-data"}});
  return r.data;
}

export async function getRecords(limit=50, type=null) {
  let url = `${BASE}/records/list?limit=${limit}`;
  if (type) url += `&type=${type}`;
  const r = await axios.get(url);
  return r.data;
}

export async function deleteRecord(id) {
  const r = await axios.delete(`${BASE}/records/${id}`);
  return r.data;
}

export async function postCameraFrame(blob, filename="frame.jpg") {
  const f = new FormData();
  f.append("file", blob, filename);
  const r = await axios.post(`${BASE}/camera/frame`, f, { headers: {"Content-Type": "multipart/form-data"}});
  return r.data;
}

export async function saveCameraClip(file) {
  const f = new FormData();
  f.append("file", file);
  const r = await axios.post(`${BASE}/camera/save`, f, { headers: {"Content-Type": "multipart/form-data"}});
  return r.data;
}
