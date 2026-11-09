<script setup lang="ts">
import { ref } from 'vue'
import ModalShell from './ModalShell.vue'

const props = withDefaults(
  defineProps<{
    title: string
    message?: string
    reasonRequired?: boolean
    reasonLabel?: string
    reasonPlaceholder?: string
    confirmLabel?: string
    danger?: boolean
    busy?: boolean
  }>(),
  {
    message: '',
    reasonRequired: false,
    reasonLabel: '原因',
    reasonPlaceholder: '请填写原因…',
    confirmLabel: '确认',
    danger: false,
    busy: false,
  },
)

const emit = defineEmits<{
  (event: 'confirm', reason: string): void
  (event: 'close'): void
}>()

const reason = ref('')

function submit() {
  if (props.reasonRequired && !reason.value.trim()) return
  emit('confirm', reason.value.trim())
}
</script>

<template>
  <ModalShell :title="title" @close="emit('close')">
    <div class="modal-head">
      <h2>{{ title }}</h2>
      <button class="modal-close" type="button" aria-label="关闭" @click="emit('close')">✕</button>
    </div>
    <div v-if="message" class="muted">{{ message }}</div>
    <label v-if="reasonRequired" class="field">
      <span>{{ reasonLabel }}<i class="req">*</i></span>
      <textarea v-model="reason" rows="3" :placeholder="reasonPlaceholder" />
      <span class="field-help">原因会写入操作日志，便于后续追溯。</span>
    </label>
    <div class="toolbar" style="margin: 0; justify-content: flex-end">
      <button class="outline" type="button" @click="emit('close')">取消</button>
      <button
        class="primary"
        type="button"
        :class="{ danger }"
        :disabled="busy || (reasonRequired && !reason.trim())"
        @click="submit"
      >
        {{ busy ? '处理中…' : confirmLabel }}
      </button>
    </div>
  </ModalShell>
</template>

<style scoped>
.primary.danger {
  background: var(--danger);
  border-color: var(--danger);
}
</style>
