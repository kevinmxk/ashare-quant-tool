<template>
  <div>
    <!-- 搜索栏 -->
    <div class="flex items-center gap-3 mb-5">
      <input
        v-model="symbolInput"
        @keyup.enter="handleSearch"
        placeholder="输入股票代码，如 600519"
        class="bg-panel border border-line rounded-lg px-4 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-blue w-64"
      />
      <button
        @click="handleSearch"
        class="bg-blue hover:bg-blue/80 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
      >
        诊断
      </button>
      <select
        v-model="strategy"
        class="bg-panel border border-line rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-blue"
      >
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <LoadingSpinner v-if="loading" text="正在诊断..." />
    <ErrorAlert v-else-if="error" title="诊断失败" :message="error" />

    <template v-else-if="result">
      <!-- Hero Card -->
      <div class="bg-panel border border-line rounded-xl p-5 mb-4">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div class="text-[10px] font-bold text-muted uppercase tracking-wider">个股诊断</div>
            <div class="text-2xl font-bold text-text mt-1">{{ result.quote.name }}</div>
            <div class="text-sm text-muted mt-1">
              {{ result.quote.symbol }}
              <span v-if="result.quote.sector" class="text-blue ml-2">{{ result.quote.sector }}</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-3xl font-bold text-text">{{ result.quote.latest_price.toFixed(2) }}</div>
            <div
              class="text-base font-semibold mt-1"
              :class="result.quote.pct_change >= 0 ? 'text-green' : 'text-red'"
            >
              {{ result.quote.pct_change >= 0 ? '+' : '' }}{{ result.quote.pct_change.toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>

      <!-- Top Metrics -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <MetricCard label="总分" :value="result.factors.total_score.toFixed(1)" />
        <MetricCard label="当前价" :value="result.quote.latest_price.toFixed(2)" />
        <MetricCard
          label="涨跌幅"
          :value="(result.quote.pct_change >= 0 ? '+' : '') + result.quote.pct_change.toFixed(2) + '%'"
        />
        <MetricCard label="可执行" :value="result.factors.eligible ? '是' : '否'" />
        <MetricCard label="PI 指数" :value="(result.factors.profitability_index ?? 0).toFixed(1)" />
      </div>

      <div class="flex gap-4 flex-col lg:flex-row">
        <!-- Left: Kline + Factors -->
        <div class="flex-1 min-w-0">
          <div class="text-[10px] font-bold text-muted uppercase tracking-wider mb-2">近60日走势</div>
          <KlineChart :data="bars" :height="380" />

          <!-- Factor Detail Metrics -->
          <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
            <MetricCard label="20日动量" :value="result.factors.momentum_20d.toFixed(2)" />
            <MetricCard label="趋势强度" :value="result.factors.trend_strength.toFixed(2)" />
            <MetricCard label="流动性" :value="result.factors.liquidity_score.toFixed(2)" />
            <MetricCard label="估值评分" :value="result.factors.valuation_score.toFixed(2)" />
            <MetricCard label="风险评分" :value="result.factors.risk_score.toFixed(2)" />
          </div>
        </div>

        <!-- Right: Signals + Lists -->
        <div class="w-full lg:w-80 shrink-0 space-y-3">
          <div class="bg-panel border-l-4 border-green rounded-xl p-4 border-y border-r border-line">
            <div class="text-[10px] font-bold text-muted uppercase tracking-wider mb-1">入场信号</div>
            <div class="text-sm text-text leading-relaxed">{{ result.factors.entry_signal }}</div>
          </div>
          <div class="bg-panel border-l-4 border-red rounded-xl p-4 border-y border-r border-line">
            <div class="text-[10px] font-bold text-muted uppercase tracking-wider mb-1">退出信号</div>
            <div class="text-sm text-text leading-relaxed">{{ result.factors.exit_signal }}</div>
          </div>

          <!-- Collapsible lists -->
          <details class="bg-panel border border-line rounded-xl overflow-hidden">
            <summary class="px-4 py-3 text-sm font-semibold text-text cursor-pointer hover:bg-panel2 transition-colors">
              核心解释 ({{ result.factors.explanations.length }})
            </summary>
            <ul class="px-4 pb-3 space-y-1">
              <li v-for="(item, idx) in result.factors.explanations" :key="idx" class="text-sm text-muted">{{ item }}</li>
              <li v-if="!result.factors.explanations.length" class="text-sm text-muted">暂无强信号。</li>
            </ul>
          </details>

          <details class="bg-panel border border-line rounded-xl overflow-hidden">
            <summary class="px-4 py-3 text-sm font-semibold text-text cursor-pointer hover:bg-panel2 transition-colors">
              未通过过滤 ({{ result.factors.failed_filters.length }})
            </summary>
            <ul class="px-4 pb-3 space-y-1">
              <li v-for="(item, idx) in result.factors.failed_filters" :key="idx" class="text-sm text-red">{{ item }}</li>
              <li v-if="!result.factors.failed_filters.length" class="text-sm text-green">全部通过。</li>
            </ul>
          </details>

          <details class="bg-panel border border-line rounded-xl overflow-hidden">
            <summary class="px-4 py-3 text-sm font-semibold text-text cursor-pointer hover:bg-panel2 transition-colors">
              风险提示 ({{ result.factors.risk_flags.length }})
            </summary>
            <ul class="px-4 pb-3 space-y-1">
              <li v-for="(item, idx) in result.factors.risk_flags" :key="idx" class="text-sm text-amber">{{ item }}</li>
              <li v-if="!result.factors.risk_flags.length" class="text-sm text-muted">无额外风险。</li>
            </ul>
          </details>
        </div>
      </div>

      <!-- Raw JSON -->
      <details class="bg-panel border border-line rounded-xl overflow-hidden mt-4">
        <summary class="px-4 py-3 text-sm font-semibold text-muted cursor-pointer hover:bg-panel2 transition-colors">
          查看原始 JSON 数据
        </summary>
        <pre class="px-4 pb-3 text-xs text-muted overflow-auto max-h-96">{{ JSON.stringify(result, null, 2) }}</pre>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import client from '../api/client'
import type { DiagnosisResult, BarDataPoint, Strategy } from '../api/types'
import MetricCard from '../components/MetricCard.vue'
import KlineChart from '../components/KlineChart.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'

const route = useRoute()
const symbolInput = ref('600519')
const strategy = ref('trend')
const strategies = ref<Strategy[]>([])
const loading = ref(false)
const error = ref('')
const result = ref<DiagnosisResult | null>(null)
const bars = ref<BarDataPoint[]>([])

async function loadStrategies() {
  try {
    const res = await client.get('/api/strategies')
    strategies.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function fetchDiagnosis(symbol: string) {
  loading.value = true
  error.value = ''
  try {
    const [diagRes, barsRes] = await Promise.all([
      client.get(`/api/stocks/${symbol}`, { params: { strategy: strategy.value } }),
      client.get(`/api/stocks/${symbol}/bars`, { params: { lookback: 60 } }),
    ])
    result.value = diagRes.data
    bars.value = barsRes.data.bars
    symbolInput.value = symbol
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '请求失败'
    result.value = null
    bars.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  const s = symbolInput.value.trim()
  if (s) fetchDiagnosis(s)
}

watch(strategy, () => {
  if (result.value) {
    fetchDiagnosis(result.value.quote.symbol)
  }
})

watch(() => route.query.symbol, (val) => {
  if (val && typeof val === 'string') {
    fetchDiagnosis(val)
  }
})

onMounted(() => {
  loadStrategies()
  const qSymbol = route.query.symbol
  if (qSymbol && typeof qSymbol === 'string') {
    fetchDiagnosis(qSymbol)
  } else {
    fetchDiagnosis(symbolInput.value)
  }
})
</script>
