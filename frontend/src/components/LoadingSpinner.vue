<template>
  <div class="flex items-center justify-center py-10">
    <div class="w-8 h-8 border-2 border-line border-t-blue rounded-full animate-spin"></div>
    <span v-if="text" class="ml-3 text-sm text-muted">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ text?: string }>()
</script>
