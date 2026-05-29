<template>
  <div>
    <div class="flex items-center gap-3 mb-5">
      <select v-model="strategy" class="bg-panel border border-line rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-blue">
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <input v-model.number="limit" type="number" min="10" max="50" step="5" class="bg-panel border border-line rounded-lg px-3 py-2 text-sm text-text w-20" />
      <button @click="fetchRankings" class="bg-blue hover:bg-blue/80 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors">刷新</button>
    </div>

    <LoadingSpinner v-if="loading" text="正在加载榜单..." />
    <ErrorAlert v-else-if="error" title="加载失败" :message="error" />

    <template v-else-if="data">
      <!-- Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <MetricCard label="样本数" :value="data.summary.total" />
        <MetricCard label="可执行" :value="data.summary.eligible_count" />
        <MetricCard label="均分" :value="data.summary.avg_score.toFixed(2)" />
        <MetricCard label="最高分" :value="data.summary.top_score.toFixed(2)" />
      </div>

      <!-- Table -->
      <div class="bg-panel border border-line rounded-xl overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-bg">
                <th v-for="col in columns" :key="col.key" @click="sortBy(col.key)" class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider cursor-pointer select-none whitespace-nowrap">
                  {{ col.label }}
                  <span v-if="sortKey === col.key" class="ml-1">{{ sortDesc ? '↓' : '↑' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sortedRows" :key="row.symbol" class="border-b border-line hover:bg-panel2 transition-colors">
                <td class="px-4 py-3 text-muted">{{ row.rank }}</td>
                <td class="px-4 py-3 font-medium text-text">{{ row.symbol }}</td>
                <td class="px-4 py-3 text-text">{{ row.name }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <div class="w-16 h-1.5 bg-line rounded-full overflow-hidden">
                      <div class="h-full bg-blue rounded-full" :style="{ width: row.score + '%' }"></div>
                    </div>
                    <span class="font-semibold text-text">{{ row.score.toFixed(1) }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 font-medium" :class="row.pct_change >= 0 ? 'text-green' : 'text-red'">
                  {{ row.pct_change >= 0 ? '+' : '' }}{{ row.pct_change.toFixed(2) }}%
                </td>
                <td class="px-4 py-3 text-muted">{{ row.sector }}</td>
                <td class="px-4 py-3 text-muted max-w-xs truncate">{{ row.entry_signal }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import client from '../api/client'
import type { RankingsTableResponse, Strategy, RankingRow } from '../api/types'
import MetricCard from '../components/MetricCard.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'

const strategy = ref('trend')
const limit = ref(20)
const strategies = ref<Strategy[]>([])
const loading = ref(false)
const error = ref('')
const data = ref<RankingsTableResponse | null>(null)
const sortKey = ref<keyof RankingRow>('rank')
const sortDesc = ref(false)

const columns = [
  { key: 'rank', label: '排名' },
  { key: 'symbol', label: '代码' },
  { key: 'name', label: '名称' },
  { key: 'score', label: '总分' },
  { key: 'pct_change', label: '涨跌幅' },
  { key: 'sector', label: '板块' },
  { key: 'entry_signal', label: '入场提示' },
]

async function loadStrategies() {
  try {
    const res = await client.get('/api/strategies')
    strategies.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function fetchRankings() {
  loading.value = true
  error.value = ''
  try {
    const res = await client.get('/api/rankings', { params: { limit: limit.value, strategy: strategy.value } })
    data.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '请求失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

function sortBy(key: string) {
  if (sortKey.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = key as keyof RankingRow
    sortDesc.value = false
  }
}

const sortedRows = computed(() => {
  if (!data.value) return []
  const rows = [...data.value.rows]
  rows.sort((a, b) => {
    const av = a[sortKey.value]
    const bv = b[sortKey.value]
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDesc.value ? bv - av : av - bv
    }
    return sortDesc.value
      ? String(bv).localeCompare(String(av))
      : String(av).localeCompare(String(bv))
  })
  return rows
})

onMounted(() => {
  loadStrategies()
  fetchRankings()
})
</script>
