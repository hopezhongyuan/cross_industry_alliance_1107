<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{
  (event: 'change', payload: { page: number; pageSize: number }): void
}>()

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.pageSize))))

const pageItems = computed<Array<number | 'gap'>>(() => {
  const count = pageCount.value
  const current = props.page
  if (count <= 7) return Array.from({ length: count }, (_, index) => index + 1)
  const items: Array<number | 'gap'> = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(count - 1, current + 1)
  if (start > 2) items.push('gap')
  for (let value = start; value <= end; value += 1) items.push(value)
  if (end < count - 1) items.push('gap')
  items.push(count)
  return items
})

function go(target: number) {
  if (target < 1 || target > pageCount.value || target === props.page) return
  emit('change', { page: target, pageSize: props.pageSize })
}

function changeSize(event: Event) {
  const size = Number((event.target as HTMLSelectElement).value)
  emit('change', { page: 1, pageSize: size })
}
</script>

<template>
  <div class="pager">
    <span class="pager-total">共 {{ total }} 条</span>
    <select :value="pageSize" aria-label="每页条数" @change="changeSize">
      <option v-for="size in [10, 20, 50, 100]" :key="size" :value="size">每页 {{ size }} 条</option>
    </select>
    <button type="button" :disabled="page <= 1" aria-label="上一页" @click="go(page - 1)">上一页</button>
    <template v-for="(item, index) in pageItems" :key="`${item}-${index}`">
      <span v-if="item === 'gap'" class="muted">…</span>
      <button v-else type="button" :class="{ on: item === page }" @click="go(item)">{{ item }}</button>
    </template>
    <button type="button" :disabled="page >= pageCount" aria-label="下一页" @click="go(page + 1)">下一页</button>
    <span class="muted">{{ page }} / {{ pageCount }} 页</span>
  </div>
</template>
