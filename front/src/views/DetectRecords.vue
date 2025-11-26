<template>
  <div>
    <h2>识别历史</h2>
    <el-button @click="load">刷新</el-button>
    <el-table :data="records" style="width:100%; margin-top:12px">
      <el-table-column prop="id" label="ID" width="80"/>
      <el-table-column prop="type" label="类型" width="120" />
      <el-table-column prop="filename" label="文件名" />
      <el-table-column prop="detect_time" label="时间" width="180" />
      <el-table-column label="操作" width="220">
        <template #default="{row}">
          <el-button size="small" @click="viewResult(row.id)">查看结果</el-button>
          <el-button size="small" type="primary" @click="viewSource(row.id)">查看原始</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getRecords } from '../api'

const records = ref([])

async function load(){
  records.value = await getRecords(100)
}

function viewResult(id){
  window.open(`http://localhost:8000/api/records/file/${id}?which=result`, "_blank")
}
function viewSource(id){
  window.open(`http://localhost:8000/api/records/file/${id}?which=source`, "_blank")
}

load()
</script>
