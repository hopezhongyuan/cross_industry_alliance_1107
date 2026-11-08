<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type AdminCategory } from '../api'
import MediaPicker from '../components/MediaPicker.vue'
import ModalShell from '../components/ModalShell.vue'

const rows = ref<AdminCategory[]>([])
const loading = ref(false)
const error = ref('')

const editorOpen = ref(false)
const editing = ref<AdminCategory | null>(null)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  name: '',
  parent_id: '',
  icon_url: '',
  sort: '0',
  status: 'ENABLED',
})

function resetForm() {
  form.name = ''
  form.parent_id = ''
  form.icon_url = ''
  form.sort = '0'
  form.status = 'ENABLED'
  formError.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.adminCategories()
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  resetForm()
  editorOpen.value = true
}

function openEdit(row: AdminCategory) {
  editing.value = row
  resetForm()
  form.name = row.name
  form.parent_id = row.parent ? String(row.parent) : ''
  form.icon_url = row.icon_url
  form.sort = String(row.sort)
  form.status = row.status
  editorOpen.value = true
}

async function submit() {
  formError.value = ''
  if (!form.name.trim()) {
    formError.value = '请填写类目名称'
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      icon_url: form.icon_url.trim(),
      sort: Number(form.sort || 0),
      status: form.status,
      parent_id: editing.value ? editing.value.parent : form.parent_id ? Number(form.parent_id) : null,
    }
    if (editing.value) {
      await api.updateCategory(editing.value.id, payload)
    } else {
      await api.createCategory(payload)
    }
    editorOpen.value = false
    await load()
  } catch (exc) {
    formError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row: AdminCategory) {
  error.value = ''
  try {
    await api.updateCategory(row.id, {
      name: row.name,
      icon_url: row.icon_url,
      sort: row.sort,
      status: row.status === 'ENABLED' ? 'DISABLED' : 'ENABLED',
      parent_id: row.parent,
    })
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  }
}

onMounted(load)
</script>

<template>
  <h1>商品类目</h1>
  <div class="toolbar">
    <span class="muted">平台统一类目，最多两级；所有商户共用。有二级类目的父类不能直接挂商品。</span>
    <button class="primary" style="margin-left: auto" @click="openCreate">新增类目</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr><th>类目名称</th><th>层级</th><th>上级类目</th><th class="money">排序</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.name }}</td>
          <td>{{ row.level === 1 ? '一级' : '二级' }}</td>
          <td>{{ row.parent_name || '-' }}</td>
          <td class="money">{{ row.sort }}</td>
          <td>
            <span :class="row.status === 'ENABLED' ? 'tag ok' : 'tag danger'">
              {{ row.status === 'ENABLED' ? '启用' : '停用' }}
            </span>
          </td>
          <td>
            <button class="text" @click="openEdit(row)">编辑</button>
            <button class="text" style="margin-left: 8px" @click="toggleStatus(row)">
              {{ row.status === 'ENABLED' ? '停用' : '启用' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无类目' }}</div>
  </div>

  <ModalShell v-if="editorOpen" :title="editing ? '编辑类目' : '新增类目'" @close="editorOpen = false">
    <h2>{{ editing ? '编辑类目' : '新增类目' }}</h2>
    <div v-if="formError" class="error" role="alert">{{ formError }}</div>
    <label class="field">
      <span>类目名称</span>
      <input v-model="form.name" name="category_name" autocomplete="off" placeholder="如：餐饮…" />
    </label>
    <label v-if="!editing" class="field">
      <span>上级类目</span>
      <select v-model="form.parent_id" name="parent_id">
        <option value="">无（一级类目）</option>
        <option v-for="row in rows.filter((item) => item.level === 1)" :key="row.id" :value="String(row.id)">
          {{ row.name }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>图标</span>
      <MediaPicker v-model="form.icon_url" kind="IMAGE" />
    </label>
    <label class="field">
      <span>排序</span>
      <input v-model="form.sort" name="sort" type="number" inputmode="numeric" />
    </label>
    <label class="field">
      <span>状态</span>
      <select v-model="form.status" name="status">
        <option value="ENABLED">启用</option>
        <option value="DISABLED">停用</option>
      </select>
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="submit">保存</button>
      <button class="text" @click="editorOpen = false">取消</button>
    </div>
  </ModalShell>
</template>
