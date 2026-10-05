<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <section class="empty-state">
    <p class="eyebrow">即将实现</p>
    <h1>{{ title }}</h1>
    <p>该页面会随处理引擎和任务系统一起接入。</p>
  </section>
</template>
