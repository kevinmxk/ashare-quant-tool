<template>
  <div class="bg-red/10 border border-red/30 rounded-xl p-4 text-sm text-red">
    <div class="font-semibold mb-1">{{ title }}</div>
    <div class="opacity-90">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; message: string }>()
</script>
