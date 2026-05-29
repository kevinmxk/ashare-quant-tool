<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-text">自选池</h2>
        <p class="mt-1 text-sm text-muted">启动后自动加载已保存的股票，新增股票只诊断当前这一只。</p>
      </div>
      <select
        v-model="strategy"
        class="bg-panel border border-line rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-blue"
        @change="reloadRows"
      >
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <ErrorAlert v-if="error" title="自选池加载失败" :message="error" />

    <LoadingSpinner v-if="loadingList" text="正在加载自选股列表..." />

    <div v-else-if="symbols.length" class="bg-panel border border-line rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full min-w-[860px] text-sm">
          <thead>
            <tr class="border-b border-line bg-bg">
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">代码</th>
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">名称</th>
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">总分</th>
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">当前价</th>
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">涨跌幅</th>
              <th class="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-wider">入场提示</th>
              <th class="px-4 py-3 text-right text-[10px] font-bold text-muted uppercase tracking-wider">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="symbol in symbols" :key="symbol" class="border-b border-line hover:bg-panel2 transition-colors">
              <td class="px-4 py-3 font-medium text-text">
                <router-link :to="`/diagnosis?symbol=${symbol}`" class="hover:text-blue transition-colors">
                  {{ symbol }}
                </router-link>
              </td>
              <template v-if="rowMap[symbol]">
                <td class="px-4 py-3 text-text">{{ rowMap[symbol].name }}</td>
                <td class="px-4 py-3 font-semibold text-text">{{ formatScore(rowMap[symbol].score) }}</td>
                <td class="px-4 py-3 text-muted">{{ rowMap[symbol].latest_price }}</td>
                <td class="px-4 py-3 font-medium" :class="pctColor(rowMap[symbol].pct_change)">
                  {{ rowMap[symbol].pct_change }}
                </td>
                <td class="px-4 py-3 text-muted max-w-md truncate">{{ rowMap[symbol].entry_signal }}</td>
              </template>
              <template v-else>
                <td colspan="5" class="px-4 py-3 text-muted">
                  {{ loadingRows[symbol] ? '正在诊断...' : rowErrors[symbol] || '等待加载' }}
                </td>
              </template>
              <td class="px-4 py-3 text-right">
                <button
                  class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line text-muted hover:border-red hover:text-red transition-colors disabled:opacity-50"
                  :disabled="removing[symbol]"
                  :title="`删除 ${symbol}`"
                  @click="removeSymbol(symbol)"
                >
                  <Trash2 class="h-4 w-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="bg-panel border border-line rounded-xl px-6 py-10 text-center text-sm text-muted">
      暂无自选股，请在下方添加单个股票代码。
    </div>

    <form class="bg-panel border border-line rounded-xl p-4" @submit.prevent="addSymbol">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          v-model="input"
          placeholder="添加自选股，如 600519"
          class="bg-bg border border-line rounded-lg px-4 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-blue flex-1"
          :disabled="adding"
        />
        <button
          type="submit"
          class="inline-flex items-center justify-center gap-2 bg-blue hover:bg-blue/80 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
          :disabled="adding"
        >
          <Plus class="h-4 w-4" />
          {{ adding ? '添加中...' : '添加自选股' }}
        </button>
      </div>
      <p v-if="addError" class="mt-3 text-sm text-red">{{ addError }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import client from '../api/client'
import type {
  Strategy,
  WatchlistAddResponse,
  WatchlistListResponse,
  WatchlistResponse,
  WatchlistRow,
} from '../api/types'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'

const input = ref('')
const strategy = ref('trend')
const strategies = ref<Strategy[]>([])
const symbols = ref<string[]>([])
const loadingList = ref(false)
const adding = ref(false)
const error = ref('')
const addError = ref('')
const rowMap = reactive<Record<string, WatchlistRow>>({})
const loadingRows = reactive<Record<string, boolean>>({})
const rowErrors = reactive<Record<string, string>>({})
const removing = reactive<Record<string, boolean>>({})

async function loadStrategies() {
  try {
    const res = await client.get<Strategy[]>('/api/strategies')
    strategies.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function loadWatchlist() {
  loadingList.value = true
  error.value = ''
  try {
    const res = await client.get<WatchlistListResponse>('/api/watchlist/list')
    symbols.value = res.data.symbols
    symbols.value.forEach((symbol) => loadRow(symbol))
  } catch (e: any) {
    error.value = e.message || '请求失败'
  } finally {
    loadingList.value = false
  }
}

async function loadRow(symbol: string) {
  loadingRows[symbol] = true
  rowErrors[symbol] = ''
  try {
    const res = await client.post<WatchlistResponse>('/api/watchlist', {
      symbols: [symbol],
      strategy: strategy.value,
    })
    const row = res.data.rows[0]
    if (row) {
      rowMap[symbol] = row
    }
  } catch (e: any) {
    rowErrors[symbol] = e.message || '诊断失败'
  } finally {
    loadingRows[symbol] = false
  }
}

async function reloadRows() {
  symbols.value.forEach((symbol) => {
    delete rowMap[symbol]
    loadRow(symbol)
  })
}

async function addSymbol() {
  const symbol = normalizeInput(input.value)
  addError.value = ''
  if (!symbol) {
    addError.value = '请输入单个股票代码'
    return
  }
  if (symbols.value.includes(symbol)) {
    addError.value = '该股票已在自选池中'
    return
  }

  adding.value = true
  try {
    const res = await client.post<WatchlistAddResponse>('/api/watchlist/add', {
      symbol,
      strategy: strategy.value,
    })
    const savedSymbol = res.data.symbol
    if (!symbols.value.includes(savedSymbol)) {
      symbols.value = [...symbols.value, savedSymbol]
    }
    rowMap[savedSymbol] = res.data.row
    input.value = ''
  } catch (e: any) {
    addError.value = e.message || '添加失败'
  } finally {
    adding.value = false
  }
}

async function removeSymbol(symbol: string) {
  removing[symbol] = true
  try {
    await client.delete(`/api/watchlist/remove/${symbol}`)
    symbols.value = symbols.value.filter((item) => item !== symbol)
    delete rowMap[symbol]
    delete loadingRows[symbol]
    delete rowErrors[symbol]
  } catch (e: any) {
    rowErrors[symbol] = e.message || '删除失败'
  } finally {
    removing[symbol] = false
  }
}

function normalizeInput(value: string): string {
  const trimmed = value.trim().toUpperCase()
  if (!trimmed || /[,，\s]/.test(trimmed)) return ''
  return trimmed
}

function formatScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : '-'
}

function pctColor(val: string | number): string {
  const v = typeof val === 'number' ? val : parseFloat(String(val))
  if (Number.isNaN(v)) return 'text-muted'
  return v >= 0 ? 'text-green' : 'text-red'
}

onMounted(() => {
  loadStrategies()
  loadWatchlist()
})
</script>
