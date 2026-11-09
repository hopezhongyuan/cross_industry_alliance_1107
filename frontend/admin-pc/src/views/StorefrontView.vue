<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  api,
  ApiError,
  type AdminMerchantRow,
  type AdminProductRow,
  type CategoryRow,
  type DecoPagePayload,
  type DecoPageRow,
  type StoreNavItem,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LinkTargetEditor from '../components/LinkTargetEditor.vue'
import MediaPicker from '../components/MediaPicker.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime } from '../format'

const router = useRouter()

const tab = ref<'NAV' | 'PAGES'>('NAV')
const navItems = ref<StoreNavItem[]>([])
const pages = ref<DecoPageRow[]>([])
const categories = ref<CategoryRow[]>([])
const merchants = ref<AdminMerchantRow[]>([])
const products = ref<AdminProductRow[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const deleting = ref<DecoPageRow | null>(null)
const submitting = ref(false)

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [nav, pageResult, cats, merchantResult, productResult] = await Promise.all([
      api.adminStoreNav(),
      api.adminDecoPages({ page_size: 100 }),
      api.adminCategories(),
      api.adminMerchants({ page: 1, page_size: 100 }),
      api.adminProducts({ page: 1, page_size: 100 }),
    ])
    navItems.value = nav
    pages.value = pageResult.items
    categories.value = cats
    merchants.value = merchantResult.items
    products.value = productResult.items
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function addNav() {
  if (navItems.value.length >= 5) {
    error.value = '底部导航最多 5 项'
    return
  }
  navItems.value.push({
    title: `导航${navItems.value.length + 1}`,
    icon_selected: '',
    icon_unselected: '',
    link_type: 'FUNCTION',
    link_value: 'HOME',
    status: 'ENABLED',
  })
}

function moveNav(index: number, offset: number) {
  const target = index + offset
  if (target < 0 || target >= navItems.value.length) return
  const list = [...navItems.value]
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  navItems.value = list
}

function removeNav(index: number) {
  navItems.value.splice(index, 1)
}

async function saveNav() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    if (!navItems.value.length) throw new Error('至少配置 1 项底部导航')
    navItems.value = await api.saveAdminStoreNav(navItems.value)
    message.value = '底部导航已保存'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : String(exc)
  } finally {
    saving.value = false
  }
}

async function createPage() {
  error.value = ''
  message.value = ''
  const payload: DecoPagePayload = {
    slug: `page-${Date.now()}`,
    title: '未命名微页面',
    share_title: '',
    share_image: '',
    draft_components: [],
  }
  try {
    const created = await api.createDecoPage(payload)
    router.push(`/storefront/pages/${created.id}`)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '新建微页面失败'
  }
}

async function submitDelete() {
  if (!deleting.value) return
  submitting.value = true
  error.value = ''
  try {
    await api.deleteDecoPage(deleting.value.id)
    deleting.value = null
    message.value = '微页面已删除'
    pages.value = (await api.adminDecoPages({ page_size: 100 })).items
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '删除失败'
  } finally {
    submitting.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <PageHeader title="店铺装修" description="平台商城统一装修：底部导航最多 5 项，微页面发布后消费者端读取发布快照。">
    <template #actions>
      <button v-if="tab === 'PAGES'" class="primary" @click="createPage">新建微页面</button>
    </template>
  </PageHeader>

  <div class="chips" style="margin-bottom: 16px">
    <button class="chip" :class="{ on: tab === 'NAV' }" @click="tab = 'NAV'">底部导航</button>
    <button class="chip" :class="{ on: tab === 'PAGES' }" @click="tab = 'PAGES'">微页面</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>

  <template v-if="tab === 'NAV'">
    <div class="card">
      <div class="section-title" style="margin-top: 0">底部导航（最多 5 项）</div>
      <div class="muted" style="margin-bottom: 12px">
        图标来自素材库；链接仅支持功能页、微页面、类目、商户、商品。保存后消费者端生效。
      </div>
      <div v-for="(item, index) in navItems" :key="index" class="deco-nav-row">
        <div class="form-grid">
          <label class="field">
            <span>名称</span>
            <input v-model="item.title" name="nav_title" autocomplete="off" placeholder="如：首页…" />
          </label>
          <label class="field">
            <span>状态</span>
            <select v-model="item.status">
              <option value="ENABLED">启用</option>
              <option value="DISABLED">停用</option>
            </select>
          </label>
          <div class="field">
            <span>选中图标</span>
            <MediaPicker v-model="item.icon_selected" kind="IMAGE" hint="81×81 PNG 透明底，≤40KB" />
          </div>
          <div class="field">
            <span>未选中图标</span>
            <MediaPicker v-model="item.icon_unselected" kind="IMAGE" hint="81×81 PNG 透明底，≤40KB" />
          </div>
        </div>
        <div class="field" style="margin-top: 10px">
          <span>跳转目标</span>
          <LinkTargetEditor
            :model-value="{ type: item.link_type, value: item.link_value }"
            :pages="pages"
            :categories="categories"
            :merchants="merchants"
            :products="products"
            @update:model-value="item.link_type = $event.type; item.link_value = $event.value"
          />
        </div>
        <div class="toolbar" style="margin: 10px 0 0">
          <button class="text" :disabled="index === 0" @click="moveNav(index, -1)">上移</button>
          <button class="text" :disabled="index === navItems.length - 1" @click="moveNav(index, 1)">下移</button>
          <button class="danger" @click="removeNav(index)">删除</button>
        </div>
      </div>
      <div class="toolbar" style="margin-bottom: 0">
        <button class="outline" :disabled="navItems.length >= 5" @click="addNav">新增导航</button>
        <button class="primary" :disabled="saving || loading" @click="saveNav">
          {{ saving ? '保存中…' : '保存导航' }}
        </button>
      </div>
    </div>
  </template>

  <template v-else>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>标题</th><th>slug</th><th>状态</th><th class="money">组件</th><th>更新时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in pages" :key="row.id">
            <td>{{ row.title }}</td>
            <td>{{ row.slug }}</td>
            <td><StatusTag :status="row.status" /></td>
            <td class="money">{{ row.component_count }}</td>
            <td>{{ formatDateTime(row.updated_at) }}</td>
            <td>
              <div class="actions">
                <button class="text" @click="router.push(`/storefront/pages/${row.id}`)">编辑</button>
                <button class="danger" @click="deleting = row">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!pages.length" class="empty">{{ loading ? '加载中…' : '暂无微页面' }}</div>
    </div>
  </template>

  <ConfirmDialog
    v-if="deleting"
    title="删除微页面"
    :message="`删除「${deleting.title}」后不可恢复，已发布地址将立即失效。`"
    confirm-label="删除"
    danger
    :busy="submitting"
    @confirm="submitDelete"
    @close="deleting = null"
  />
</template>
