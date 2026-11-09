<script setup lang="ts">
import { computed } from 'vue'

const STATUS_MAP: Record<string, { label: string; tone: string }> = {
  ACTIVE: { label: '正常', tone: 'ok' },
  RESTING: { label: '停业', tone: 'warn' },
  BANNED: { label: '已封禁', tone: 'danger' },
  PENDING: { label: '待处理', tone: 'warn' },
  PENDING_PAYMENT: { label: '待支付', tone: 'warn' },
  PENDING_ACCEPT: { label: '待接单', tone: 'warn' },
  PENDING_FULFILL: { label: '待履约', tone: 'warn' },
  PENDING_AUDIT: { label: '待审核', tone: 'warn' },
  PROCESSING: { label: '处理中', tone: 'info' },
  FULFILLING: { label: '履约中', tone: 'info' },
  COMPLETED: { label: '已完成', tone: 'ok' },
  SETTLED: { label: '已结算', tone: 'ok' },
  AFTER_SALE: { label: '售后中', tone: 'danger' },
  REFUNDING: { label: '退款中', tone: 'warn' },
  REFUNDED: { label: '已退款', tone: 'neutral' },
  CLOSED: { label: '已关闭', tone: 'neutral' },
  CANCELLED: { label: '已取消', tone: 'neutral' },
  DRAFT: { label: '草稿', tone: 'neutral' },
  ON_SALE: { label: '在售', tone: 'ok' },
  OFF_SALE: { label: '已下架', tone: 'neutral' },
  REJECTED: { label: '已驳回', tone: 'danger' },
  APPROVED: { label: '已通过', tone: 'ok' },
  PUBLISHED: { label: '已发布', tone: 'ok' },
  ENABLED: { label: '启用', tone: 'ok' },
  DISABLED: { label: '停用', tone: 'neutral' },
  PAID: { label: '已打款', tone: 'ok' },
  REQUESTED: { label: '待打款', tone: 'warn' },
  PAYING: { label: '打款中', tone: 'info' },
  FAILED: { label: '失败', tone: 'danger' },
  FROZEN: { label: '冻结', tone: 'warn' },
}

const props = defineProps<{
  status: string
  label?: string
  tone?: string
}>()

const meta = computed(() => STATUS_MAP[props.status] ?? { label: props.status, tone: 'neutral' })
const text = computed(() => props.label ?? meta.value.label)
const tone = computed(() => props.tone ?? meta.value.tone)
</script>

<template>
  <span class="tag" :class="tone">{{ text }}</span>
</template>
