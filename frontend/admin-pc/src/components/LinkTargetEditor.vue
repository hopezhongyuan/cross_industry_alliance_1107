<script setup lang="ts">
import { computed } from 'vue'

type LinkValue = { type: string; value: string }
type Option = { value: string; label: string }

const props = defineProps<{
  modelValue: LinkValue
  pages: Array<{ slug: string; title: string }>
  categories: Array<{ id: number; name: string; level: number }>
  merchants: Array<{ id: number; name: string }>
  products: Array<{ id: number; title: string }>
}>()

const emit = defineEmits<{ (event: 'update:modelValue', value: LinkValue): void }>()

const FUNCTION_OPTIONS: Option[] = [
  { value: 'HOME', label: '首页' },
  { value: 'CATEGORY', label: '商品分类' },
  { value: 'CART', label: '购物车' },
  { value: 'ORDERS', label: '订单列表' },
  { value: 'ME', label: '个人中心' },
  { value: 'SEARCH', label: '搜索' },
  { value: 'MERCHANT_LIST', label: '商家列表' },
]

const types = [
  { value: 'FUNCTION', label: '功能页面' },
  { value: 'MICRO_PAGE', label: '微页面' },
  { value: 'CATEGORY', label: '商品类目' },
  { value: 'MERCHANT', label: '商户' },
  { value: 'PRODUCT', label: '商品' },
]

const options = computed<Option[]>(() => {
  if (props.modelValue.type === 'FUNCTION') return FUNCTION_OPTIONS
  if (props.modelValue.type === 'MICRO_PAGE') {
    return props.pages.map((page) => ({ value: page.slug, label: `${page.title}（${page.slug}）` }))
  }
  if (props.modelValue.type === 'CATEGORY') {
    return props.categories.map((item) => ({
      value: String(item.id),
      label: `${item.level === 2 ? '　' : ''}${item.name}`,
    }))
  }
  if (props.modelValue.type === 'MERCHANT') {
    return props.merchants.map((item) => ({ value: String(item.id), label: item.name }))
  }
  return props.products.map((item) => ({ value: String(item.id), label: item.title }))
})

function changeType(value: string) {
  const nextOptions = value === 'FUNCTION' ? FUNCTION_OPTIONS : []
  const fallback = value === 'FUNCTION' ? 'HOME' : ''
  emit('update:modelValue', { type: value, value: nextOptions.length ? fallback : fallback })
}

function changeValue(value: string) {
  emit('update:modelValue', { ...props.modelValue, value })
}
</script>

<template>
  <div class="link-target">
    <select :value="modelValue.type" @change="changeType(($event.target as HTMLSelectElement).value)">
      <option v-for="item in types" :key="item.value" :value="item.value">{{ item.label }}</option>
    </select>
    <select :value="modelValue.value" @change="changeValue(($event.target as HTMLSelectElement).value)">
      <option value="">请选择目标…</option>
      <option v-for="item in options" :key="item.value" :value="item.value">{{ item.label }}</option>
    </select>
  </div>
</template>
