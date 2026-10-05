<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">Watermark Remover</RouterLink>
      <nav aria-label="主导航">
        <RouterLink to="/">处理文件</RouterLink>
        <RouterLink to="/tasks">任务</RouterLink>
        <RouterLink to="/settings">设置</RouterLink>
      </nav>
    </header>
    <main><RouterView /></main>
  </div>
</template>
