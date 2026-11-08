<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError } from '../api'

const router = useRouter()
const phone = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await api.login(phone.value.trim(), password.value)
    router.push('/')
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="card" style="width: 360px; display: flex; flex-direction: column; gap: 14px">
    <h1 style="margin-bottom: 0">平台后台登录</h1>
    <div class="field">
      <span>手机号</span>
      <input v-model="phone" autocomplete="username" placeholder="管理员手机号" />
    </div>
    <div class="field">
      <span>密码</span>
      <input v-model="password" type="password" autocomplete="current-password" placeholder="密码" />
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <button class="primary" :disabled="loading || !phone || !password" @click="submit">
      {{ loading ? '登录中…' : '登录' }}
    </button>
  </div>
</template>
