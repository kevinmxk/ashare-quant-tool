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
              <th class="w-10 px-2 py-3 text-center text-[10px] font-bold text-muted uppercase tracking-wider"></th>
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
            <template v-for="symbol in symbols" :key="symbol">
              <tr class="border-b border-line hover:bg-panel2 transition-colors">
                <td class="px-2 py-3 text-center">
                  <button
                    class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:text-blue transition-colors"
                    :class="{ 'text-blue bg-panel2': expandedSymbol === symbol }"
                    :title="expandedSymbol === symbol ? '收起走势' : '展开走势'"
                    @click="toggleChart(symbol)"
                  >
                    <TrendingUp v-if="expandedSymbol !== symbol" class="h-4 w-4" />
                    <ChevronUp v-else class="h-4 w-4" />
                  </button>
                </td>
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
              <tr>
                <td colspan="8" class="p-0">
                  <div
                    class="overflow-hidden transition-all duration-300 ease-out"
                    :class="expandedSymbol === symbol ? 'max-h-[130px] opacity-100' : 'max-h-0 opacity-0'"
                  >
                    <div class="px-4 py-3 bg-panel2 border-b border-line h-[100px]">
                      <div v-if="loadingBars[symbol]" class="h-full flex items-center justify-center">
                        <Loader2 class="h-5 w-5 text-muted animate-spin" />
                      </div>
                      <MiniChart v-else-if="barsMap[symbol]" :data="barsMap[symbol]" />
                      <div v-else class="h-full flex items-center justify-center text-sm text-muted">
                        暂无数据
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
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
import { Plus, Trash2, TrendingUp, ChevronUp, Loader2 } from 'lucide-vue-next'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'
import MiniChart from '../components/MiniChart.vue'
import { useWatchlist } from '../composables/useWatchlist'

const {
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
} = useWatchlist()

void loadStrategies
void loadWatchlist
void normalizeInput
</script>
