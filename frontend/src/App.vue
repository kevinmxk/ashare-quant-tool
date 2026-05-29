<template>
  <div class="flex h-screen bg-bg text-text">
    <AppSidebar :current-route="$route.name as string" />
    <div class="flex-1 flex flex-col overflow-hidden">
      <main class="flex-1 overflow-y-auto p-5">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from './components/AppSidebar.vue'
</script>
