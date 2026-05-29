<template>
  <div>
    <div class="flex items-center gap-3 mb-5">
      <input
        v-model="input"
        placeholder="输入股票代码，逗号分隔，如 600519,300750"
        class="bg-panel border border-line rounded-lg px-4 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-blue flex-1 max-w-lg"
      />
      <select v-model="strategy" class="bg-panel border border-line rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-blue">
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button @click="fetchWatchlist" class="bg-blue hover:bg-blue/80 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors">诊断</button>
    </div>

    <LoadingSpinner v-if="loading" text="正在加载自选池..." />
    <ErrorAlert v-else-if="error" title="加载失败" :message="error" />

    <template v-else-if="rows.length">
      <div class="bg-panel border border-line rounded-xl overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-bg">
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">代码</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">名称</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">总分</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">最新价</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">涨跌幅</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">可执行</th>
                <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">入场提示</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.symbol" class="border-b border-line hover:bg-panel2 transition-colors">
                <td class="px-4 py-3 font-medium text-text">
                  <router-link :to="`/diagnosis?symbol=${row.symbol}`" class="hover:text-blue transition-colors">{{ row.symbol }}</router-link>
                </td>
                <td class="px-4 py-3 text-text">{{ row.name }}</td>
                <td class="px-4 py-3 font-semibold text-text">{{ row.score.toFixed(1) }}</td>
                <td class="px-4 py-3 text-muted">{{ row.latest_price }}</td>
                <td class="px-4 py-3 font-medium" :class="pctColor(row.pct_change)">{{ row.pct_change }}</td>
                <td class="px-4 py-3">
                  <span :class="row.eligible === '是' ? 'text-green' : 'text-amber'">{{ row.eligible }}</span>
                </td>
                <td class="px-4 py-3 text-muted max-w-sm truncate">{{ row.entry_signal }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <div v-else-if="!loading && !error" class="text-sm text-muted py-8 text-center">
      输入股票代码并点击诊断，即可查看自选池对比。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '../api/client'
import type { WatchlistRow, Strategy } from '../api/types'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'

const input = ref('600519,300750,000858,002594,688981')
const strategy = ref('trend')
const strategies = ref<Strategy[]>([])
const loading = ref(false)
const error = ref('')
const rows = ref<WatchlistRow[]>([])

async function loadStrategies() {
  try {
    const res = await client.get('/api/strategies')
    strategies.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function fetchWatchlist() {
  const symbols = input.value.split(',').map(s => s.trim()).filter(Boolean)
  if (!symbols.length) return
  loading.value = true
  error.value = ''
  try {
    const res = await client.post('/api/watchlist', { symbols, strategy: strategy.value })
    rows.value = res.data.rows
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '请求失败'
    rows.value = []
  } finally {
    loading.value = false
  }
}

function pctColor(val: string): string {
  const v = parseFloat(val)
  if (isNaN(v)) return 'text-muted'
  return v >= 0 ? 'text-green' : 'text-red'
}

onMounted(() => {
  loadStrategies()
  fetchWatchlist()
})
</script>
