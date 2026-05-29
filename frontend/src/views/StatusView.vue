<template>
  <div>
    <LoadingSpinner v-if="loading" text="正在加载状态..." />
    <ErrorAlert v-else-if="error" title="加载失败" :message="error" />

    <template v-else-if="status">
      <!-- Top Metrics -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
        <MetricCard label="配置数据源" :value="status.configured_provider" />
        <MetricCard label="实际生效" :value="status.active_provider_chain || status.active_provider" />
        <MetricCard label="持久缓存" :value="status.persistent_cache_enabled ? '开启' : '关闭'" />
      </div>

      <div class="flex gap-4 flex-col lg:flex-row">
        <!-- Routes Table -->
        <div class="flex-1 bg-panel border border-line rounded-xl overflow-hidden">
          <div class="px-4 py-3 border-b border-line text-[10px] font-bold text-muted uppercase tracking-wider">数据路由表</div>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-bg">
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">模块</th>
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">数据源</th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-b border-line">
                <td class="px-4 py-2 text-text">榜单</td>
                <td class="px-4 py-2 text-muted">{{ status.provider_routes?.ranking || '-' }}</td>
              </tr>
              <tr class="border-b border-line">
                <td class="px-4 py-2 text-text">单股诊断</td>
                <td class="px-4 py-2 text-muted">{{ status.provider_routes?.diagnosis || '-' }}</td>
              </tr>
              <tr>
                <td class="px-4 py-2 text-text">自选池</td>
                <td class="px-4 py-2 text-muted">{{ status.provider_routes?.watchlist || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Strategies -->
        <div class="flex-1 bg-panel border border-line rounded-xl overflow-hidden">
          <div class="px-4 py-3 border-b border-line text-[10px] font-bold text-muted uppercase tracking-wider">策略列表</div>
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-bg">
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">策略</th>
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in status.strategies" :key="s.id" class="border-b border-line">
                <td class="px-4 py-2 text-text font-medium">{{ s.name }}</td>
                <td class="px-4 py-2 text-muted">{{ s.description || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Provider Diagnostics -->
      <details v-if="status.provider_diagnostics?.length" class="bg-panel border border-line rounded-xl overflow-hidden mt-4">
        <summary class="px-4 py-3 text-sm font-semibold text-text cursor-pointer hover:bg-panel2 transition-colors">
          Provider Diagnostics ({{ status.provider_diagnostics.length }})
        </summary>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-line bg-bg">
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">Provider</th>
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">状态</th>
                <th class="px-4 py-2 text-left text-[10px] font-bold text-muted uppercase tracking-wider">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(d, idx) in status.provider_diagnostics" :key="idx" class="border-b border-line">
                <td class="px-4 py-2 text-text">{{ d.provider }}</td>
                <td class="px-4 py-2">
                  <span :class="d.enabled ? 'text-green' : 'text-red'">{{ d.enabled ? '正常' : '不可用' }}</span>
                </td>
                <td class="px-4 py-2 text-muted">{{ d.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      <!-- Cache Info -->
      <details v-if="status.cache" class="bg-panel border border-line rounded-xl overflow-hidden mt-4">
        <summary class="px-4 py-3 text-sm font-semibold text-text cursor-pointer hover:bg-panel2 transition-colors">缓存详情</summary>
        <pre class="px-4 pb-3 text-xs text-muted overflow-auto max-h-60">{{ JSON.stringify(status.cache, null, 2) }}</pre>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '../api/client'
import type { StatusResponse } from '../api/types'
import MetricCard from '../components/MetricCard.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ErrorAlert from '../components/ErrorAlert.vue'

const loading = ref(false)
const error = ref('')
const status = ref<StatusResponse | null>(null)

async function fetchStatus() {
  loading.value = true
  error.value = ''
  try {
    const res = await client.get('/api/status')
    status.value = res.data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '请求失败'
    status.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchStatus()
})
</script>
