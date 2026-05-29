<template>
  <aside class="w-64 bg-bg border-r border-line flex flex-col shrink-0">
    <div class="p-5 border-b border-line">
      <div class="text-lg font-bold tracking-wider text-text">A-QUANT</div>
      <div class="text-xs text-muted mt-1">量化分析终端</div>
    </div>
    <nav class="flex-1 p-3 space-y-1">
      <router-link
        v-for="item in menu"
        :key="item.name"
        :to="item.path"
        :class="[
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
          currentRoute === item.name
            ? 'bg-panel2 text-blue'
            : 'text-muted hover:text-text hover:bg-panel',
        ]"
      >
        <component :is="item.icon" class="w-4 h-4" />
        {{ item.label }}
      </router-link>
    </nav>
    <div class="p-4 border-t border-line">
      <div class="text-[10px] text-muted opacity-60">v2.0.0 · FastAPI + Vue 3</div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { Activity, BarChart3, List, Settings } from 'lucide-vue-next'

defineProps<{ currentRoute: string }>()

const menu = [
  { name: 'Diagnosis', label: '个股诊断', path: '/diagnosis', icon: Activity },
  { name: 'Rankings', label: '策略榜单', path: '/rankings', icon: BarChart3 },
  { name: 'Watchlist', label: '自选池', path: '/watchlist', icon: List },
  { name: 'Status', label: '系统状态', path: '/status', icon: Settings },
]
</script>
