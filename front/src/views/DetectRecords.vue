<template>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
    <h2 style="flex-grow: 1; text-align: center; margin: 0;">识别历史</h2>
    <el-button @click="load">刷新</el-button>
  </div>

  <el-table
    :data="records"
    v-loading="loading"
    style="width: 100%"
    table-layout="fixed"
  >
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="type" label="类型" width="120" />
    <el-table-column prop="filename" label="文件名" width="200" show-overflow-tooltip />
    <el-table-column prop="detect_time" label="时间" width="180" />
    <el-table-column label="操作" width="320">
      <template #default="{ row }">
        <el-button size="small" @click="viewResult(row.id)">查看结果</el-button>
        <el-button size="small" type="primary" @click="viewSource(row.id)">查看原始</el-button>
        <el-button size="small" type="danger" @click="handleDeleteRecord(row.id)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-pagination
    v-model:current-page="page"
    :page-size="limit"
    :total="total"
    @current-change="onPageChange"
    layout="total, prev, pager, next"
    style="margin-top: 12px; text-align: center"
  />
</template>

<script setup>
import { ElMessageBox, ElMessage } from 'element-plus'
import { getRecordsPaged, deleteRecord } from '../api'
import { usePagination } from '@/composables/usePagination'
import { useRouter } from 'vue-router'

const {
  data: records,
  total,
  page,
  limit,
  loading,
  load,
  onPageChange
} = usePagination(getRecordsPaged)


const router = useRouter()

async function handleDeleteRecord(id) {
  try {
    await ElMessageBox.confirm('确定要删除这条记录吗？删除后无法恢复。', '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })

    await deleteRecord(id)

    records.value = records.value.filter(record => record.id !== id)
    if (records.value.length === 0 && page.value > 1) {
      page.value--
      load()
    }

    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 👇 修改：使用 router 跳转
function viewResult(id) {
  router.push(`/records/${id}/result`)
}

function viewSource(id) {
  router.push(`/records/${id}/source`)
}
</script>