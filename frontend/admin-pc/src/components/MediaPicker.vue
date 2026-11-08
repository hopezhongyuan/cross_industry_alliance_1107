<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError, type MediaAsset, type MediaFolder } from '../api'
import ModalShell from './ModalShell.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string | string[]
    kind?: 'IMAGE' | 'VIDEO' | ''
    multiple?: boolean
  }>(),
  { kind: '', multiple: false },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string | string[]): void
}>()

const open = ref(false)
const loading = ref(false)
const error = ref('')
const folders = ref<MediaFolder[]>([])
const assets = ref<MediaAsset[]>([])
const activeFolder = ref('all')
const keyword = ref('')
const selected = ref<string[]>([])
const fileInput = ref<HTMLInputElement | null>(null)

function currentUrls(): string[] {
  return Array.isArray(props.modelValue) ? props.modelValue : props.modelValue ? [props.modelValue] : []
}

async function loadFolders() {
  folders.value = await api.mediaFolders()
}

async function loadAssets() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.mediaAssets({
      folder: activeFolder.value === 'all' ? undefined : activeFolder.value,
      kind: props.kind || undefined,
      q: keyword.value || undefined,
      page_size: 60,
    })
    assets.value = result.items
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载素材失败'
  } finally {
    loading.value = false
  }
}

async function show() {
  open.value = true
  selected.value = currentUrls()
  activeFolder.value = 'all'
  keyword.value = ''
  try {
    await Promise.all([loadFolders(), loadAssets()])
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载素材失败'
  }
}

function selectFolder(value: string) {
  activeFolder.value = value
  loadAssets()
}

function toggle(asset: MediaAsset) {
  if (!props.multiple) {
    selected.value = [asset.url]
    return
  }
  if (selected.value.includes(asset.url)) {
    selected.value = selected.value.filter((url) => url !== asset.url)
  } else {
    selected.value = [...selected.value, asset.url]
  }
}

function confirm() {
  emit('update:modelValue', props.multiple ? selected.value : selected.value[0] ?? '')
  open.value = false
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await api.uploadMediaAsset(file, activeFolder.value !== 'all' && activeFolder.value !== 'none' ? Number(activeFolder.value) : null)
    input.value = ''
    await loadAssets()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '上传失败'
  }
}
</script>

<template>
  <div class="media-picker">
    <button class="text" type="button" @click="show">从素材库选择</button>
    <div v-if="currentUrls().length" class="media-selected">
      <img v-for="url in currentUrls()" :key="url" :src="url" alt="已选素材" class="media-thumb" />
    </div>

    <ModalShell v-if="open" title="选择素材" wide @close="open = false">
      <h2>选择素材</h2>
      <div class="toolbar" style="margin: 0">
        <button class="chip" :class="{ on: activeFolder === 'all' }" @click="selectFolder('all')">全部</button>
        <button class="chip" :class="{ on: activeFolder === 'none' }" @click="selectFolder('none')">未分类</button>
        <button
          v-for="folder in folders"
          :key="folder.id"
          class="chip"
          :class="{ on: activeFolder === String(folder.id) }"
          @click="selectFolder(String(folder.id))"
        >
          {{ folder.name }}<em>{{ folder.asset_count }}</em>
        </button>
        <button class="primary" style="margin-left: auto" @click="fileInput?.click()">上传素材</button>
        <input ref="fileInput" type="file" hidden accept="image/*,video/*" @change="upload" />
      </div>

      <div class="toolbar" style="margin: 0">
        <label class="field">
          <span>搜索</span>
          <input v-model="keyword" name="media_q" placeholder="素材名称…" @keyup.enter="loadAssets" />
        </label>
        <button class="primary" :disabled="loading" @click="loadAssets">查询</button>
        <span class="muted">已选 {{ selected.length }} 个</span>
      </div>

      <div v-if="error" class="error" role="alert">{{ error }}</div>

      <div class="media-grid">
        <button
          v-for="asset in assets"
          :key="asset.id"
          class="media-item"
          :class="{ on: selected.includes(asset.url) }"
          type="button"
          @click="toggle(asset)"
        >
          <img v-if="asset.kind === 'IMAGE'" :src="asset.url" :alt="asset.name" />
          <span v-else class="media-video">视频</span>
          <small>{{ asset.name }}</small>
        </button>
      </div>
      <div v-if="loading" class="muted">加载中…</div>
      <div v-else-if="!assets.length" class="empty">该条件下暂无素材，请先上传</div>

      <div class="toolbar" style="margin: 0">
        <button class="primary" :disabled="!selected.length" @click="confirm">确认选择</button>
        <button class="text" @click="open = false">取消</button>
      </div>
    </ModalShell>
  </div>
</template>
