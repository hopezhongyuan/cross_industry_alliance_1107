<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="page-head">
    <div class="page-head-body">
      <h1>{{ title }}</h1>
      <div v-if="description" class="page-sub">{{ description }}</div>
    </div>
    <div class="page-head-actions">
      <slot name="actions" />
    </div>
  </div>
</template>
