<template>
  <div class="bg-panel border border-line rounded-xl p-4 min-h-[88px]">
    <div class="text-[10px] font-bold text-muted uppercase tracking-wider">{{ label }}</div>
    <div class="text-xl font-bold text-text mt-1">{{ value }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: string | number }>()
</script>
