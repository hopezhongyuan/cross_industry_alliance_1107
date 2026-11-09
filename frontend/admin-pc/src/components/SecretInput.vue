<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: string
  configured: boolean
  masked: string
  label: string
  help?: string
  placeholder?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const editing = ref(false)
const revealed = ref(false)

function startEdit() {
  editing.value = true
  revealed.value = false
  emit('update:modelValue', '')
}

function cancelEdit() {
  editing.value = false
  revealed.value = false
  emit('update:modelValue', '')
}

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="field">
    <span>{{ label }} <em class="tag" :class="configured ? 'ok' : 'warn'">{{ configured ? '已配置' : '未配置' }}</em></span>
    <div v-if="configured && !editing" class="secret-row">
      <span class="secret-value">{{ masked || '••••••••' }}</span>
      <button class="outline" type="button" @click="startEdit">更换</button>
    </div>
    <template v-else>
      <div class="secret-row">
        <input
          :type="revealed ? 'text' : 'password'"
          :value="modelValue"
          autocomplete="new-password"
          :placeholder="placeholder || '请输入新的值…'"
          style="flex: 1"
          @input="onInput"
        />
        <button class="text" type="button" @click="revealed = !revealed">{{ revealed ? '隐藏' : '显示' }}</button>
        <button v-if="configured" class="text" type="button" @click="cancelEdit">取消</button>
      </div>
      <span class="field-help">留空保存表示保持原值；保存后只显示掩码与尾 4 位。</span>
    </template>
    <span v-if="help && !editing" class="field-help">{{ help }}</span>
  </div>
</template>
