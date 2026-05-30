import { onMounted, onUnmounted, reactive, ref } from 'vue'
import client from '../api/client'
import type {
  Strategy,
  WatchlistAddResponse,
  WatchlistListResponse,
  WatchlistResponse,
  WatchlistRow,
  BarDataPoint,
  BarsResponse,
} from '../api/types'

export function useWatchlist() {
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
  const expandedSymbol = ref<string | null>(null)
  const barsMap = reactive<Record<string, BarDataPoint[]>>({})
  const loadingBars = reactive<Record<string, boolean>>({})
  let refreshTimer: ReturnType<typeof window.setInterval> | null = null
  let refreshInFlight = false

  async function loadStrategies() {
    try {
      const res = await client.get<Strategy[]>('/api/strategies')
      strategies.value = res.data
    } catch (e) {
      console.error(e)
    }
  }

  async function loadWatchlist(options: { silent?: boolean } = {}) {
    const silent = options.silent === true
    if (!silent) {
      loadingList.value = true
    }
    error.value = ''
    try {
      const res = await client.get<WatchlistListResponse>('/api/watchlist/list')
      const nextSymbols = res.data.symbols
      symbols.value = nextSymbols
      pruneRemovedSymbols(nextSymbols)
      if (nextSymbols.length) {
        await loadRows(nextSymbols)
        await refreshLoadedBars(nextSymbols)
      }
    } catch (e: any) {
      error.value = e.message || '请求失败'
    } finally {
      if (!silent) {
        loadingList.value = false
      }
    }
  }

  async function loadRows(targetSymbols: string[]) {
    if (!targetSymbols.length) return
    targetSymbols.forEach((symbol) => {
      loadingRows[symbol] = true
      rowErrors[symbol] = ''
    })
    try {
      const res = await client.post<WatchlistResponse>('/api/watchlist', {
        symbols: targetSymbols,
        strategy: strategy.value,
      })
      const loaded = new Set<string>()
      res.data.rows.forEach((row) => {
        rowMap[row.symbol] = row
        loaded.add(row.symbol)
      })
      targetSymbols.forEach((symbol) => {
        if (!loaded.has(symbol)) {
          rowErrors[symbol] = '诊断失败'
        }
      })
    } catch (e: any) {
      targetSymbols.forEach((symbol) => {
        rowErrors[symbol] = e.message || '诊断失败'
      })
    } finally {
      targetSymbols.forEach((symbol) => {
        loadingRows[symbol] = false
      })
    }
  }

  async function toggleChart(symbol: string) {
    if (expandedSymbol.value === symbol) {
      expandedSymbol.value = null
      return
    }
    expandedSymbol.value = symbol
    if (!barsMap[symbol] || barsMap[symbol].length === 0) {
      await loadBars(symbol)
    }
  }

  async function loadBars(symbol: string) {
    loadingBars[symbol] = true
    try {
      const res = await client.get<BarsResponse>(`/api/stocks/${symbol}/bars`, {
        params: { lookback: 60 },
      })
      const allBars = res.data.bars
      barsMap[symbol] = allBars.slice(-30)
    } catch (e: any) {
      console.error(`Failed to load bars for ${symbol}`, e)
    } finally {
      loadingBars[symbol] = false
    }
  }

  async function refreshLoadedBars(activeSymbols: string[]) {
    const activeSet = new Set(activeSymbols)
    const loadedSymbols = Object.keys(barsMap).filter((symbol) => activeSet.has(symbol))
    await Promise.all(loadedSymbols.map((symbol) => loadBars(symbol)))
  }

  async function reloadRows() {
    const currentSymbols = [...symbols.value]
    currentSymbols.forEach((symbol) => {
      delete rowMap[symbol]
    })
    await loadRows(currentSymbols)
    await refreshLoadedBars(currentSymbols)
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
      delete barsMap[symbol]
      delete loadingBars[symbol]
      if (expandedSymbol.value === symbol) {
        expandedSymbol.value = null
      }
    } catch (e: any) {
      rowErrors[symbol] = e.message || '删除失败'
    } finally {
      removing[symbol] = false
    }
  }

  function pruneRemovedSymbols(activeSymbols: string[]) {
    const activeSet = new Set(activeSymbols)
    Object.keys(rowMap).forEach((symbol) => {
      if (!activeSet.has(symbol)) delete rowMap[symbol]
    })
    Object.keys(loadingRows).forEach((symbol) => {
      if (!activeSet.has(symbol)) delete loadingRows[symbol]
    })
    Object.keys(rowErrors).forEach((symbol) => {
      if (!activeSet.has(symbol)) delete rowErrors[symbol]
    })
    Object.keys(barsMap).forEach((symbol) => {
      if (!activeSet.has(symbol)) delete barsMap[symbol]
    })
    Object.keys(loadingBars).forEach((symbol) => {
      if (!activeSet.has(symbol)) delete loadingBars[symbol]
    })
    if (expandedSymbol.value && !activeSet.has(expandedSymbol.value)) {
      expandedSymbol.value = null
    }
  }

  async function pollWatchlist() {
    if (refreshInFlight) return
    refreshInFlight = true
    try {
      await loadWatchlist({ silent: true })
    } finally {
      refreshInFlight = false
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
    refreshTimer = window.setInterval(pollWatchlist, 300000)
  })

  onUnmounted(() => {
    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer)
      refreshTimer = null
    }
  })

  return {
    symbols,
    strategy,
    strategies,
    rowMap,
    loadingRows,
    rowErrors,
    removing,
    expandedSymbol,
    barsMap,
    loadingBars,
    input,
    adding,
    addError,
    loadingList,
    error,
    loadStrategies,
    loadWatchlist,
    toggleChart,
    addSymbol,
    removeSymbol,
    reloadRows,
    normalizeInput,
    formatScore,
    pctColor,
  }
}
