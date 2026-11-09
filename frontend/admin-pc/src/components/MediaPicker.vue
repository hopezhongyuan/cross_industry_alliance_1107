<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError, type MediaAsset, type MediaFolder } from '../api'
import ModalShell from './ModalShell.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string | string[]
    kind?: 'IMAGE' | 'VIDEO' | ''
    multiple?: boolean
    hint?: string
    maxSizeMb?: number
  }>(),
  { kind: '', multiple: false, hint: '', maxSizeMb: 0 },
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

const uploadState = ref<'idle' | 'uploading' | 'done' | 'failed'>('idle')
const uploadPercent = ref(0)
const uploadName = ref('')
const uploadMessage = ref('')

const sizeLimit = () => props.maxSizeMb || (props.kind === 'VIDEO' ? 20 : 5)

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
  uploadState.value = 'idle'
  uploadMessage.value = ''
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
  error.value = ''
  const maxBytes = sizeLimit() * 1024 * 1024
  if (file.size > maxBytes) {
    uploadState.value = 'failed'
    uploadName.value = file.name
    uploadMessage.value = `文件 ${(file.size / 1024 / 1024).toFixed(1)}MB，超出建议上限 ${sizeLimit()}MB`
    input.value = ''
    return
  }
  uploadState.value = 'uploading'
  uploadPercent.value = 0
  uploadName.value = file.name
  uploadMessage.value = ''
  try {
    const folderId =
      activeFolder.value !== 'all' && activeFolder.value !== 'none' ? Number(activeFolder.value) : null
    const asset = await api.uploadMediaAssetWithProgress(file, folderId, (percent) => {
      uploadPercent.value = percent
    })
    uploadState.value = 'done'
    uploadPercent.value = 100
    uploadMessage.value = `${asset.kind === 'VIDEO' ? '视频' : '图片'}已上传 · ${(asset.size / 1024).toFixed(0)}KB${
       asset.width && asset.height ? ` · ${asset.width}×${asset.height}` : ''
    }`
    input.value = ''
    await loadAssets()
    if (!props.multiple) {
      selected.value = [asset.url]
    }
  } catch (exc) {
    uploadState.value = 'failed'
    uploadMessage.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '上传失败'
    input.value = ''
  }
}

function removeSelected(url: string) {
  if (props.multiple) {
    emit(
      'update:modelValue',
      currentUrls().filter((item) => item !== url),
    )
    return
  }
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="media-picker">
    <div class="secret-row">
      <button class="outline" type="button" @click="show">从素材库选择</button>
      <button class="text" type="button" :disabled="uploadState === 'uploading'" @click="fileInput?.click()">
        上传新素材
      </button>
      <input
        ref="fileInput"
        type="file"
        hidden
        :accept="kind === 'VIDEO' ? 'video/*' : kind === 'IMAGE' ? 'image/*' : 'image/*,video/*'"
        @change="upload"
      />
    </div>
    <span v-if="hint" class="field-help">{{ hint }}</span>
    <div v-if="currentUrls().length" class="media-selected">
      <div v-for="url in currentUrls()" :key="url" class="media-selected-item">
        <img :src="url" alt="已选素材" class="media-thumb" />
        <button class="text" type="button" @click="removeSelected(url)">移除</button>
      </div>
    </div>
    <div v-if="uploadState !== 'idle'" class="upload-status" :class="uploadState">
      <template v-if="uploadState === 'uploading'">
        <span>上传中 {{ uploadPercent }}%</span>
        <span class="upload-progress"><i :style="{ width: `${uploadPercent}%` }" /></span>
      </template>
      <template v-else>
        <span>{{ uploadState === 'done' ? '✓' : '✕' }} {{ uploadName }}</span>
        <span class="muted">{{ uploadMessage }}</span>
      </template>
    </div>

    <ModalShell v-if="open" title="选择素材" wide @close="open = false">
      <div class="modal-head">
        <h2>选择素材</h2>
        <button class="modal-close" type="button" aria-label="关闭" @click="open = false">✕</button>
      </div>
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

<style scoped>
.media-selected-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
</style>
