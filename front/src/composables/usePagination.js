// src/composables/usePagination.js
import { ref } from 'vue'

export function usePagination(fetchFn) {
  const page = ref(1)
  const limit = ref(8)
  const total = ref(0)
  const loading = ref(false)
  const data = ref([])

  async function load() {
    loading.value = true
    try {
      const res = await fetchFn(page.value, limit.value)
      data.value = res.data || []
      total.value = res.total || 0
    } finally {
      loading.value = false
    }
  }

  function onPageChange(newPage) {
    page.value = newPage
    load()
  }

  load()

  return {
    page,
    limit,
    total,
    data,
    loading,
    load,
    onPageChange
  }
}