<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  api,
  ApiError,
  type AdminMerchantRow,
  type AdminProductRow,
  type CategoryRow,
  type DecoComponent,
  type DecoPageDetail,
  type DecoPagePayload,
  type DecoPageRow,
  type StoreNavItem,
} from '../api'
import LinkTargetEditor from '../components/LinkTargetEditor.vue'
import MediaPicker from '../components/MediaPicker.vue'
import ModalShell from '../components/ModalShell.vue'
import { formatDateTime } from '../format'

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

const editorOpen = ref(false)
const editingId = ref<number | null>(null)
const editorError = ref('')
const form = reactive<DecoPagePayload>({
  slug: '',
  title: '',
  share_title: '',
  share_image: '',
  draft_components: [],
})

const COMPONENT_LABEL: Record<string, string> = {
  AD: '广告',
  CAROUSEL: '轮播图',
  IMAGE_HOTSPOT: '图片热区',
  PRODUCT: '商品',
  SEARCH: '搜索框',
  LOCATION: '定位组件',
  DIVIDER: '辅助线',
  LINK: '链接',
}

const COMPONENT_TYPES = Object.keys(COMPONENT_LABEL)

function resetMessage() {
  error.value = ''
  message.value = ''
}

async function loadAll() {
  loading.value = true
  resetMessage()
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
  resetMessage()
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

function openCreatePage() {
  editingId.value = null
  form.slug = ''
  form.title = ''
  form.share_title = ''
  form.share_image = ''
  form.draft_components = []
  editorError.value = ''
  editorOpen.value = true
}

async function openEditPage(row: DecoPageRow) {
  editorError.value = ''
  try {
    const detail = await api.adminDecoPage(row.id)
    applyPage(detail)
    editorOpen.value = true
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载微页面失败'
  }
}

function applyPage(detail: DecoPageDetail) {
  editingId.value = detail.id
  form.slug = detail.slug
  form.title = detail.title
  form.share_title = detail.share_title
  form.share_image = detail.share_image
  form.draft_components = detail.draft_components.map((item) => ({
    ...item,
    config: JSON.parse(JSON.stringify(item.config || {})),
  }))
}

function newLink() {
  return { type: 'FUNCTION', value: 'HOME' }
}

function defaultConfig(type: string): Record<string, any> {
  if (type === 'AD') return { image: '', height: 180, link: newLink() }
  if (type === 'CAROUSEL') {
    return { images: [{ image: '', link: newLink() }], interval: 4, height: 220, indicator: true }
  }
  if (type === 'IMAGE_HOTSPOT') {
    return { image: '', hotspots: [{ x: 10, y: 10, w: 30, h: 10, link: newLink() }] }
  }
  if (type === 'PRODUCT') {
    return { source: 'MANUAL', product_ids: [], category_id: null, merchant_id: null, layout: 'GRID', columns: 2, limit: 6, show_sales: false }
  }
  if (type === 'SEARCH') return { placeholder: '搜索商品或门店…', hot_keywords: [], style: 'DEFAULT' }
  if (type === 'LOCATION') return { title: '附近好店', radius: 3000 }
  if (type === 'DIVIDER') return { style: 'BLANK', height: 16, color: '#E3DACB', background: '#F6F1E7' }
  return { title: '查看更多', subtitle: '', image: '', layout: 'CARD', link: newLink() }
}

function addComponent(type: string) {
  form.draft_components.push({
    id: crypto.randomUUID(),
    type,
    config: defaultConfig(type),
  })
}

function removeComponent(index: number) {
  form.draft_components.splice(index, 1)
}

function moveComponent(index: number, offset: number) {
  const target = index + offset
  if (target < 0 || target >= form.draft_components.length) return
  const list = [...form.draft_components]
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  form.draft_components = list
}

function addCarouselImage(component: DecoComponent) {
  component.config.images.push({ image: '', link: newLink() })
}

function addHotspot(component: DecoComponent) {
  component.config.hotspots.push({ x: 10, y: 10, w: 20, h: 10, link: newLink() })
}

async function saveDraft(): Promise<DecoPageDetail | null> {
  editorError.value = ''
  if (!form.slug.trim() || !form.title.trim()) {
    editorError.value = 'slug 与标题必填'
    return null
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      slug: form.slug.trim(),
      title: form.title.trim(),
      draft_components: form.draft_components,
    }
    const detail = editingId.value
      ? await api.updateDecoPage(editingId.value, payload)
      : await api.createDecoPage(payload)
    applyPage(detail)
    pages.value = (await api.adminDecoPages({ page_size: 100 })).items
    message.value = '草稿已保存'
    return detail
  } catch (exc) {
    editorError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : String(exc)
    return null
  } finally {
    saving.value = false
  }
}

async function publishPage() {
  const saved = await saveDraft()
  if (!saved) return
  saving.value = true
  try {
    const detail = await api.publishDecoPage(saved.id)
    applyPage(detail)
    pages.value = (await api.adminDecoPages({ page_size: 100 })).items
    message.value = '微页面已发布'
  } catch (exc) {
    editorError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : String(exc)
  } finally {
    saving.value = false
  }
}

async function deletePage(row: DecoPageRow) {
  if (!window.confirm(`确定删除微页面「${row.title}」吗？`)) return
  resetMessage()
  try {
    await api.deleteDecoPage(row.id)
    pages.value = (await api.adminDecoPages({ page_size: 100 })).items
    message.value = '微页面已删除'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '删除失败'
  }
}

onMounted(loadAll)
</script>

<template>
  <h1>店铺装修</h1>
  <div class="toolbar">
    <div class="chips">
      <button class="chip" :class="{ on: tab === 'NAV' }" @click="tab = 'NAV'">底部导航</button>
      <button class="chip" :class="{ on: tab === 'PAGES' }" @click="tab = 'PAGES'">微页面</button>
    </div>
    <span class="muted">平台商城统一装修</span>
  </div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="muted" aria-live="polite">{{ message }}</div>

  <template v-if="tab === 'NAV'">
    <div class="card">
      <div class="section-title">底部导航（最多 5 项）</div>
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
        </div>
        <div class="form-grid">
          <div class="field">
            <span>选中图标</span>
            <MediaPicker v-model="item.icon_selected" kind="IMAGE" />
          </div>
          <div class="field">
            <span>未选中图标</span>
            <MediaPicker v-model="item.icon_unselected" kind="IMAGE" />
          </div>
        </div>
        <div class="field">
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
        <div class="toolbar" style="margin: 0">
          <button class="text" :disabled="index === 0" @click="moveNav(index, -1)">上移</button>
          <button class="text" :disabled="index === navItems.length - 1" @click="moveNav(index, 1)">下移</button>
          <button class="danger" @click="removeNav(index)">删除</button>
        </div>
      </div>
      <div class="toolbar">
        <button class="text" :disabled="navItems.length >= 5" @click="addNav">新增导航</button>
        <button class="primary" :disabled="saving || loading" @click="saveNav">保存导航</button>
      </div>
    </div>
  </template>

  <template v-else>
    <div class="toolbar">
      <button class="primary" @click="openCreatePage">新建微页面</button>
      <span class="muted">草稿可随时保存；发布后消费者端读取发布快照。</span>
    </div>
    <div class="card" style="padding: 0">
      <table>
        <thead>
          <tr><th>标题</th><th>slug</th><th>状态</th><th>组件</th><th>更新时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in pages" :key="row.id">
            <td>{{ row.title }}</td>
            <td>{{ row.slug }}</td>
            <td><span class="tag" :class="{ ok: row.status === 'PUBLISHED' }">{{ row.status === 'PUBLISHED' ? '已发布' : '草稿' }}</span></td>
            <td>{{ row.component_count }}</td>
            <td>{{ formatDateTime(row.updated_at) }}</td>
            <td>
              <button class="text" @click="openEditPage(row)">编辑</button>
              <button class="danger" style="margin-left: 8px" @click="deletePage(row)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!pages.length" class="empty">{{ loading ? '加载中…' : '暂无微页面' }}</div>
    </div>
  </template>

  <ModalShell v-if="editorOpen" title="微页面编辑" wide @close="editorOpen = false">
    <h2>{{ editingId ? '编辑微页面' : '新建微页面' }}</h2>
    <div v-if="editorError" class="error" role="alert">{{ editorError }}</div>
    <div class="form-grid">
      <label class="field">
        <span>slug</span>
        <input v-model="form.slug" name="slug" autocomplete="off" placeholder="如：home…" />
      </label>
      <label class="field">
        <span>标题</span>
        <input v-model="form.title" name="page_title" autocomplete="off" placeholder="页面标题…" />
      </label>
      <label class="field">
        <span>分享标题</span>
        <input v-model="form.share_title" name="share_title" autocomplete="off" placeholder="选填…" />
      </label>
    </div>
    <div class="field">
      <span>分享图</span>
      <MediaPicker v-model="form.share_image" kind="IMAGE" />
    </div>

    <div class="section-title">组件库</div>
    <div class="toolbar" style="margin-top: 0">
      <button v-for="type in COMPONENT_TYPES" :key="type" class="chip" @click="addComponent(type)">
        + {{ COMPONENT_LABEL[type] }}
      </button>
    </div>

    <div v-for="(component, index) in form.draft_components" :key="component.id" class="deco-component">
      <div class="toolbar" style="margin: 0">
        <b>{{ COMPONENT_LABEL[component.type] ?? component.type }}</b>
        <div>
          <button class="text" :disabled="index === 0" @click="moveComponent(index, -1)">上移</button>
          <button class="text" :disabled="index === form.draft_components.length - 1" @click="moveComponent(index, 1)">下移</button>
          <button class="danger" @click="removeComponent(index)">删除</button>
        </div>
      </div>

      <template v-if="component.type === 'AD'">
        <div class="field"><span>广告图</span><MediaPicker v-model="component.config.image" kind="IMAGE" /></div>
        <div class="form-grid">
          <label class="field"><span>高度（px）</span><input v-model="component.config.height" type="number" /></label>
        </div>
        <div class="field">
          <span>跳转</span>
          <LinkTargetEditor v-model="component.config.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
        </div>
      </template>

      <template v-else-if="component.type === 'CAROUSEL'">
        <div v-for="(image, imageIndex) in component.config.images" :key="imageIndex" class="deco-subblock">
          <div class="field"><span>图片 {{ imageIndex + 1 }}</span><MediaPicker v-model="image.image" kind="IMAGE" /></div>
          <div class="field">
            <span>跳转</span>
            <LinkTargetEditor v-model="image.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
          </div>
          <button class="danger" @click="component.config.images.splice(imageIndex, 1)">移除图片</button>
        </div>
        <div class="toolbar" style="margin: 0">
          <button class="text" :disabled="component.config.images.length >= 8" @click="addCarouselImage(component)">添加图片</button>
        </div>
        <div class="form-grid">
          <label class="field"><span>切换间隔（秒）</span><input v-model="component.config.interval" type="number" /></label>
          <label class="field"><span>高度（px）</span><input v-model="component.config.height" type="number" /></label>
        </div>
      </template>

      <template v-else-if="component.type === 'IMAGE_HOTSPOT'">
        <div class="field"><span>底图</span><MediaPicker v-model="component.config.image" kind="IMAGE" /></div>
        <div v-for="(hotspot, hotspotIndex) in component.config.hotspots" :key="hotspotIndex" class="deco-subblock">
          <div class="form-grid">
            <label class="field"><span>X %</span><input v-model="hotspot.x" type="number" /></label>
            <label class="field"><span>Y %</span><input v-model="hotspot.y" type="number" /></label>
            <label class="field"><span>宽 %</span><input v-model="hotspot.w" type="number" /></label>
            <label class="field"><span>高 %</span><input v-model="hotspot.h" type="number" /></label>
          </div>
          <div class="field">
            <span>跳转</span>
            <LinkTargetEditor v-model="hotspot.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
          </div>
          <button class="danger" @click="component.config.hotspots.splice(hotspotIndex, 1)">移除热区</button>
        </div>
        <div class="toolbar" style="margin: 0">
          <button class="text" :disabled="component.config.hotspots.length >= 10" @click="addHotspot(component)">添加热区</button>
        </div>
      </template>

      <template v-else-if="component.type === 'PRODUCT'">
        <div class="form-grid">
          <label class="field">
            <span>商品来源</span>
            <select v-model="component.config.source">
              <option value="MANUAL">手动选品</option>
              <option value="CATEGORY">按类目</option>
              <option value="MERCHANT">按商户</option>
            </select>
          </label>
          <label class="field">
            <span>布局</span>
            <select v-model="component.config.layout"><option value="GRID">网格</option><option value="LIST">列表</option></select>
          </label>
          <label class="field">
            <span>列数 / 数量</span>
            <div style="display: flex; gap: 8px">
              <input v-model="component.config.columns" type="number" min="2" max="3" />
              <input v-model="component.config.limit" type="number" min="1" max="20" />
            </div>
          </label>
        </div>
        <label v-if="component.config.source === 'MANUAL'" class="field">
          <span>选择商品（可多选）</span>
          <select v-model="component.config.product_ids" multiple size="6">
            <option v-for="item in products" :key="item.id" :value="item.id">{{ item.title }}</option>
          </select>
        </label>
        <label v-else-if="component.config.source === 'CATEGORY'" class="field">
          <span>选择类目</span>
          <select v-model="component.config.category_id">
            <option :value="null">请选择…</option>
            <option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label v-else class="field">
          <span>选择商户</span>
          <select v-model="component.config.merchant_id">
            <option :value="null">请选择…</option>
            <option v-for="item in merchants" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </label>
        <label class="field" style="flex-direction: row; align-items: center; gap: 8px">
          <input v-model="component.config.show_sales" type="checkbox" style="width: auto" />
          <span>显示销量</span>
        </label>
      </template>

      <template v-else-if="component.type === 'SEARCH'">
        <div class="form-grid">
          <label class="field"><span>占位文案</span><input v-model="component.config.placeholder" /></label>
          <label class="field">
            <span>样式</span>
            <select v-model="component.config.style"><option value="DEFAULT">标准</option><option value="COMPACT">紧凑</option></select>
          </label>
        </div>
        <label class="field">
          <span>热搜词（逗号分隔）</span>
          <input :value="(component.config.hot_keywords || []).join('，')" @input="component.config.hot_keywords = ($event.target as HTMLInputElement).value.split(/[，,]/).map((v) => v.trim()).filter(Boolean)" />
        </label>
      </template>

      <template v-else-if="component.type === 'LOCATION'">
        <div class="form-grid">
          <label class="field"><span>标题</span><input v-model="component.config.title" /></label>
          <label class="field"><span>半径（米）</span><input v-model="component.config.radius" type="number" /></label>
        </div>
      </template>

      <template v-else-if="component.type === 'DIVIDER'">
        <div class="form-grid">
          <label class="field">
            <span>样式</span>
            <select v-model="component.config.style"><option value="BLANK">留白</option><option value="LINE">细线</option></select>
          </label>
          <label class="field"><span>高度（px）</span><input v-model="component.config.height" type="number" /></label>
          <label class="field"><span>颜色</span><input v-model="component.config.color" placeholder="#E3DACB" /></label>
          <label class="field"><span>背景</span><input v-model="component.config.background" placeholder="#F6F1E7" /></label>
        </div>
      </template>

      <template v-else-if="component.type === 'LINK'">
        <div class="form-grid">
          <label class="field"><span>标题</span><input v-model="component.config.title" /></label>
          <label class="field"><span>副标题</span><input v-model="component.config.subtitle" /></label>
          <label class="field">
            <span>样式</span>
            <select v-model="component.config.layout"><option value="CARD">卡片</option><option value="TEXT">文字</option></select>
          </label>
        </div>
        <div class="field"><span>图片（选填）</span><MediaPicker v-model="component.config.image" kind="IMAGE" /></div>
        <div class="field">
          <span>跳转</span>
          <LinkTargetEditor v-model="component.config.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
        </div>
      </template>
    </div>

    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="saveDraft">保存草稿</button>
      <button class="primary" :disabled="saving" @click="publishPage">发布</button>
      <button class="text" @click="editorOpen = false">关闭</button>
    </div>
  </ModalShell>
</template>
