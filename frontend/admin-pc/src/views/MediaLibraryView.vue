<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type MediaAsset, type MediaFolder } from '../api'
import ModalShell from '../components/ModalShell.vue'

const folders = ref<MediaFolder[]>([])
const assets = ref<MediaAsset[]>([])
const activeFolder = ref('all')
const keyword = ref('')
const kind = ref('')
const loading = ref(false)
const error = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const folderOpen = ref(false)
const editingFolder = ref<MediaFolder | null>(null)
const folderName = ref('')
const folderSort = ref('0')
const folderError = ref('')

async function loadFolders() {
  folders.value = await api.mediaFolders()
}

async function loadAssets() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.mediaAssets({
      folder: activeFolder.value === 'all' ? undefined : activeFolder.value,
      kind: kind.value || undefined,
      q: keyword.value || undefined,
      page_size: 60,
    })
    assets.value = result.items
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await Promise.all([loadFolders(), loadAssets()])
}

function selectFolder(value: string) {
  activeFolder.value = value
  loadAssets()
}

function openFolder(folder: MediaFolder | null) {
  editingFolder.value = folder
  folderName.value = folder?.name ?? ''
  folderSort.value = String(folder?.sort ?? 0)
  folderError.value = ''
  folderOpen.value = true
}

async function saveFolder() {
  if (!folderName.value.trim()) {
    folderError.value = '请填写文件夹名称'
    return
  }
  try {
    if (editingFolder.value) {
      await api.updateMediaFolder(editingFolder.value.id, {
        name: folderName.value.trim(),
        sort: Number(folderSort.value || 0),
      })
    } else {
      await api.createMediaFolder({ name: folderName.value.trim(), sort: Number(folderSort.value || 0) })
    }
    folderOpen.value = false
    await refresh()
  } catch (exc) {
    folderError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  }
}

async function removeFolder(folder: MediaFolder) {
  if (!confirm(`确定删除文件夹「${folder.name}」吗？`)) return
  try {
    await api.deleteMediaFolder(folder.id)
    await refresh()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '删除失败'
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await api.uploadMediaAsset(
      file,
      activeFolder.value !== 'all' && activeFolder.value !== 'none' ? Number(activeFolder.value) : null,
    )
    input.value = ''
    await refresh()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '上传失败'
  }
}

async function removeAsset(asset: MediaAsset) {
  if (!confirm(`确定删除素材「${asset.name}」吗？`)) return
  try {
    await api.deleteMediaAsset(asset.id)
    await refresh()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '删除失败'
  }
}

onMounted(refresh)
</script>

<template>
  <h1>素材库</h1>
  <div class="toolbar">
    <span class="muted">素材文件夹仅一级；业务字段只能引用素材库中的图片/视频，不支持外部 URL。</span>
    <button class="primary" style="margin-left: auto" @click="openFolder(null)">新增文件夹</button>
    <button class="primary" @click="fileInput?.click()">上传素材</button>
    <input ref="fileInput" type="file" hidden accept="image/*,video/*" @change="upload" />
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="media-layout">
    <aside class="card media-folders">
      <button :class="{ on: activeFolder === 'all' }" @click="selectFolder('all')">全部素材</button>
      <button :class="{ on: activeFolder === 'none' }" @click="selectFolder('none')">未分类</button>
      <div v-for="folder in folders" :key="folder.id" class="row-actions" style="display: flex; gap: 6px">
        <button style="flex: 1" :class="{ on: activeFolder === String(folder.id) }" @click="selectFolder(String(folder.id))">
          {{ folder.name }}（{{ folder.asset_count }}）
        </button>
        <button class="text" @click="openFolder(folder)">编辑</button>
        <button class="danger" @click="removeFolder(folder)">删除</button>
      </div>
    </aside>

    <section>
      <div class="toolbar" style="margin: 0 0 12px">
        <label class="field">
          <span>类型</span>
          <select v-model="kind" @change="loadAssets">
            <option value="">全部</option>
            <option value="IMAGE">图片</option>
            <option value="VIDEO">视频</option>
          </select>
        </label>
        <label class="field">
          <span>搜索</span>
          <input v-model="keyword" name="media_q" placeholder="素材名称…" @keyup.enter="loadAssets" />
        </label>
        <button class="primary" :disabled="loading" @click="loadAssets">查询</button>
      </div>

      <div class="media-grid">
        <div v-for="asset in assets" :key="asset.id" class="media-item">
          <img v-if="asset.kind === 'IMAGE'" :src="asset.url" :alt="asset.name" />
          <span v-else class="media-video">视频</span>
          <small>{{ asset.name }}</small>
          <small class="muted">{{ asset.folder_name || '未分类' }}</small>
          <div class="row-actions" style="display: flex; gap: 8px">
            <a :href="asset.url" target="_blank">查看</a>
            <button class="danger" @click="removeAsset(asset)">删除</button>
          </div>
        </div>
      </div>
      <div v-if="!assets.length" class="empty">{{ loading ? '加载中…' : '暂无素材' }}</div>
    </section>
  </div>

  <ModalShell v-if="folderOpen" :title="editingFolder ? '编辑文件夹' : '新增文件夹'" @close="folderOpen = false">
    <h2>{{ editingFolder ? '编辑文件夹' : '新增文件夹' }}</h2>
    <div v-if="folderError" class="error" role="alert">{{ folderError }}</div>
    <label class="field">
      <span>文件夹名称</span>
      <input v-model="folderName" name="folder_name" placeholder="如：商品图…" />
    </label>
    <label class="field">
      <span>排序</span>
      <input v-model="folderSort" name="folder_sort" type="number" inputmode="numeric" />
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" @click="saveFolder">保存</button>
      <button class="text" @click="folderOpen = false">取消</button>
    </div>
  </ModalShell>
</template>
