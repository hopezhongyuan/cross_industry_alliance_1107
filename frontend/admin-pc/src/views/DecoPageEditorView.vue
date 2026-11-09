<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  api,
  ApiError,
  type AdminCategory,
  type AdminMerchantRow,
  type AdminProductRow,
  type CategoryRow,
  type DecoComponent,
  type DecoPagePayload,
  type DecoPageRow,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LinkTargetEditor from '../components/LinkTargetEditor.vue'
import MediaPicker from '../components/MediaPicker.vue'
import PageHeader from '../components/PageHeader.vue'
import { formatDateTime } from '../format'

const route = useRoute()
const router = useRouter()
const pageId = computed(() => Number(route.params.id))

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

const form = reactive<DecoPagePayload & { status: string; published_at: string | null }>({
  slug: '',
  title: '',
  share_title: '',
  share_image: '',
  draft_components: [],
  status: 'DRAFT',
  published_at: null,
})

const activeIndex = ref(0)
const categories = ref<CategoryRow[]>([])
const adminCategories = ref<AdminCategory[]>([])
const merchants = ref<AdminMerchantRow[]>([])
const products = ref<AdminProductRow[]>([])
const pages = ref<DecoPageRow[]>([])
const loading = ref(true)
const saving = ref(false)
const publishing = ref(false)
const error = ref('')
const message = ref('')

const active = computed<DecoComponent | null>(() => form.draft_components[activeIndex.value] ?? null)

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
    return {
      source: 'MANUAL',
      product_ids: [],
      category_id: null,
      merchant_id: null,
      layout: 'GRID',
      columns: 2,
      limit: 6,
      show_sales: false,
    }
  }
  if (type === 'SEARCH') return { placeholder: '搜索商品或门店…', hot_keywords: [], style: 'DEFAULT' }
  if (type === 'LOCATION') return { title: '附近好店', radius: 3000 }
  if (type === 'DIVIDER') return { style: 'BLANK', height: 16, color: '#E3DACB', background: '#F6F1E7' }
  return { title: '查看更多', subtitle: '', image: '', layout: 'CARD', link: newLink() }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [detail, cats, adminCats, merchantResult, productResult, pageResult] = await Promise.all([
      api.adminDecoPage(pageId.value),
      api.categories(),
      api.adminCategories(),
      api.adminMerchants({ page: 1, page_size: 100 }),
      api.adminProducts({ page: 1, page_size: 100 }),
      api.adminDecoPages({ page_size: 100 }),
    ])
    form.slug = detail.slug
    form.title = detail.title
    form.share_title = detail.share_title
    form.share_image = detail.share_image
    form.status = detail.status
    form.published_at = detail.published_at
    form.draft_components = detail.draft_components.map((item) => ({
      ...item,
      config: JSON.parse(JSON.stringify(item.config || {})),
    }))
    categories.value = cats
    adminCategories.value = adminCats
    merchants.value = merchantResult.items
    products.value = productResult.items
    pages.value = pageResult.items
    activeIndex.value = 0
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载微页面失败'
  } finally {
    loading.value = false
  }
}

function addComponent(type: string) {
  form.draft_components.push({ id: crypto.randomUUID(), type, config: defaultConfig(type) })
  activeIndex.value = form.draft_components.length - 1
}

function removeComponent(index: number) {
  form.draft_components.splice(index, 1)
  if (activeIndex.value >= form.draft_components.length) {
    activeIndex.value = Math.max(0, form.draft_components.length - 1)
  }
}

function moveComponent(index: number, offset: number) {
  const target = index + offset
  if (target < 0 || target >= form.draft_components.length) return
  const list = [...form.draft_components]
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  form.draft_components = list
  activeIndex.value = target
}

function addCarouselImage(component: DecoComponent) {
  component.config.images.push({ image: '', link: newLink() })
}

function addHotspot(component: DecoComponent) {
  component.config.hotspots.push({ x: 10, y: 10, w: 20, h: 10, link: newLink() })
}

function productById(id: number): AdminProductRow | undefined {
  return products.value.find((item) => item.id === id)
}

function previewProducts(component: DecoComponent): AdminProductRow[] {
  const config = component.config
  if (config.source === 'MANUAL') {
    return (config.product_ids || [])
      .map((id: number) => productById(id))
      .filter((item: AdminProductRow | undefined): item is AdminProductRow => Boolean(item))
      .slice(0, config.limit || 6)
  }
  if (config.source === 'CATEGORY' && config.category_id) {
    return products.value.filter((item) => item.category_id === config.category_id).slice(0, config.limit || 6)
  }
  if (config.source === 'MERCHANT' && config.merchant_id) {
    return products.value.filter((item) => item.merchant_id === config.merchant_id).slice(0, config.limit || 6)
  }
  return []
}

async function save(nextStatus?: string) {
  error.value = ''
  message.value = ''
  if (!form.slug.trim() || !form.title.trim()) {
    error.value = 'slug 与标题必填'
    return null
  }
  saving.value = true
  try {
    const payload: DecoPagePayload = {
      slug: form.slug.trim(),
      title: form.title.trim(),
      share_title: form.share_title,
      share_image: form.share_image,
      draft_components: form.draft_components,
    }
    const detail = await api.updateDecoPage(pageId.value, payload)
    form.status = detail.status
    form.published_at = detail.published_at
    message.value = '草稿已保存'
    if (nextStatus === 'PUBLISHED') return detail
    return detail
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
    return null
  } finally {
    saving.value = false
  }
}

async function saveDraft() {
  await save()
}

async function publish() {
  const saved = await save()
  if (!saved) return
  publishing.value = true
  error.value = ''
  try {
    const detail = await api.publishDecoPage(saved.id)
    form.status = detail.status
    form.published_at = detail.published_at
    message.value = '微页面已发布，消费者端已生效'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '发布失败'
  } finally {
    publishing.value = false
  }
}

const routeHref = computed(() => `/pages/micro/index?slug=${form.slug}`)
const leaveConfirm = ref(false)

onMounted(load)
</script>

<template>
  <PageHeader :title="`微页面编辑 · ${form.title || '未命名'}`" :description="`${form.slug} · ${form.status === 'PUBLISHED' ? '已发布' : '草稿'}`">
    <template #actions>
      <button class="outline" @click="leaveConfirm = true">返回列表</button>
      <button class="outline" :disabled="saving" @click="saveDraft">{{ saving ? '保存中…' : '保存草稿' }}</button>
      <button class="primary" :disabled="publishing || saving" @click="publish">
        {{ publishing ? '发布中…' : '发布' }}
      </button>
    </template>
  </PageHeader>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>
  <div v-if="loading" class="empty">加载中…</div>

  <template v-if="!loading">
    <div class="card" style="margin-bottom: 16px">
      <div class="form-grid">
        <label class="field">
          <span>页面 slug<i class="req">*</i></span>
          <input v-model="form.slug" name="slug" autocomplete="off" placeholder="如：home…" />
          <span class="field-help">发布后消费者端路径为 {{ routeHref }}</span>
        </label>
        <label class="field">
          <span>页面标题<i class="req">*</i></span>
          <input v-model="form.title" name="page_title" autocomplete="off" placeholder="页面标题…" />
        </label>
        <label class="field">
          <span>分享标题</span>
          <input v-model="form.share_title" name="share_title" autocomplete="off" placeholder="选填…" />
        </label>
        <div class="field">
          <span>分享图</span>
          <MediaPicker v-model="form.share_image" kind="IMAGE" hint="建议 1080×720（3:2），≤500KB" />
        </div>
      </div>
      <div class="muted" style="margin-top: 8px">
        状态：{{ form.status === 'PUBLISHED' ? '已发布' : '草稿' }}
        <span v-if="form.published_at"> · 上次发布 {{ formatDateTime(form.published_at) }}</span>
      </div>
    </div>

    <div class="editor-layout">
      <aside class="editor-column">
        <div class="section-title" style="margin-top: 0">组件列表</div>
        <div class="component-list">
          <button
            v-for="(component, index) in form.draft_components"
            :key="component.id"
            class="component-item"
            :class="{ on: index === activeIndex }"
            type="button"
            @click="activeIndex = index"
          >
            <b>{{ COMPONENT_LABEL[component.type] ?? component.type }}</b>
            <span class="muted">#{{ index + 1 }}</span>
          </button>
          <div v-if="!form.draft_components.length" class="empty" style="padding: 20px 8px">暂无组件</div>
        </div>
        <div class="section-title">组件库</div>
        <div class="component-add">
          <button v-for="type in COMPONENT_TYPES" :key="type" class="chip" @click="addComponent(type)">
            + {{ COMPONENT_LABEL[type] }}
          </button>
        </div>
      </aside>

      <section class="preview-column">
        <div class="section-title" style="margin-top: 0">预览</div>
        <div class="phone-frame">
          <div v-if="!form.draft_components.length" class="preview-empty">添加组件后在此预览</div>
          <div
            v-for="component in form.draft_components"
            :key="component.id"
            class="preview-block"
            :style="component.type === 'DIVIDER' ? { background: component.config.background || '#F6F1E7' } : undefined"
          >
            <template v-if="component.type === 'AD'">
              <img v-if="component.config.image" :src="component.config.image" class="preview-image" :style="{ height: `${component.config.height || 180}px` }" alt="广告" />
              <div v-else class="preview-placeholder" :style="{ height: `${component.config.height || 180}px` }">广告图未选择</div>
            </template>
            <template v-else-if="component.type === 'CAROUSEL'">
              <img
                v-if="component.config.images?.[0]?.image"
                :src="component.config.images[0].image"
                class="preview-image"
                :style="{ height: `${component.config.height || 220}px` }"
                alt="轮播"
              />
              <div v-else class="preview-placeholder" :style="{ height: `${component.config.height || 220}px` }">
                轮播图未选择（{{ component.config.images?.length || 0 }} 张）
              </div>
            </template>
            <template v-else-if="component.type === 'IMAGE_HOTSPOT'">
              <div v-if="component.config.image" class="preview-hotspot">
                <img :src="component.config.image" class="preview-image" alt="热区底图" />
                <span
                  v-for="(hotspot, hIndex) in component.config.hotspots"
                  :key="hIndex"
                  class="preview-hotspot-area"
                  :style="{
                    left: `${hotspot.x}%`,
                    top: `${hotspot.y}%`,
                    width: `${hotspot.w}%`,
                    height: `${hotspot.h}%`,
                  }"
                />
              </div>
              <div v-else class="preview-placeholder" style="height: 220px">热区底图未选择</div>
            </template>
            <template v-else-if="component.type === 'PRODUCT'">
              <div class="preview-products" :class="{ list: component.config.layout === 'LIST' }">
                <div v-for="product in previewProducts(component)" :key="product.id" class="preview-product">
                  <div class="preview-product-cover">{{ product.title.slice(0, 1) }}</div>
                  <span>{{ product.title }}</span>
                  <b>¥{{ (product.price / 100).toFixed(2) }}</b>
                </div>
                <div v-if="!previewProducts(component).length" class="preview-empty">未匹配到商品</div>
              </div>
            </template>
            <template v-else-if="component.type === 'SEARCH'">
              <div class="preview-search">{{ component.config.placeholder || '搜索' }}</div>
            </template>
            <template v-else-if="component.type === 'LOCATION'">
              <div class="preview-location">
                <b>{{ component.config.title || '附近好店' }}</b>
                <span class="muted">半径 {{ component.config.radius || 3000 }} 米</span>
              </div>
            </template>
            <template v-else-if="component.type === 'DIVIDER'">
              <div :style="{ height: `${component.config.height || 16}px` }" />
            </template>
            <template v-else-if="component.type === 'LINK'">
              <div class="preview-link">
                <b>{{ component.config.title || '查看更多' }}</b>
                <span>{{ component.config.subtitle || '›' }}</span>
              </div>
            </template>
          </div>
        </div>
        <div class="muted" style="margin-top: 8px">预览为简化示意，最终以消费者端渲染为准。</div>
      </section>

      <aside class="editor-column">
        <div class="section-title" style="margin-top: 0">属性面板</div>
        <div v-if="active" class="card attr-card">
          <div class="toolbar" style="margin-bottom: 12px">
            <b>{{ COMPONENT_LABEL[active.type] ?? active.type }}</b>
            <span class="spacer" style="flex: 1" />
            <button class="text" :disabled="activeIndex === 0" @click="moveComponent(activeIndex, -1)">上移</button>
            <button
              class="text"
              :disabled="activeIndex === form.draft_components.length - 1"
              @click="moveComponent(activeIndex, 1)"
            >
              下移
            </button>
            <button class="danger" @click="removeComponent(activeIndex)">删除</button>
          </div>

          <template v-if="active.type === 'AD'">
            <div class="field">
              <span>广告图</span>
              <MediaPicker v-model="active.config.image" kind="IMAGE" hint="建议 1080×540（2:1），≤500KB" />
            </div>
            <label class="field">
              <span>高度（px）</span>
              <input v-model="active.config.height" type="number" min="60" max="600" />
            </label>
            <div class="field">
              <span>跳转</span>
              <LinkTargetEditor v-model="active.config.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
            </div>
          </template>

          <template v-else-if="active.type === 'CAROUSEL'">
            <div v-for="(image, imageIndex) in active.config.images" :key="imageIndex" class="deco-subblock">
              <div class="field">
                <span>图片 {{ imageIndex + 1 }}</span>
                <MediaPicker v-model="image.image" kind="IMAGE" hint="建议 1080×540，≤500KB" />
              </div>
              <div class="field">
                <span>跳转</span>
                <LinkTargetEditor v-model="image.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
              </div>
              <button class="danger" @click="active.config.images.splice(imageIndex, 1)">移除图片</button>
            </div>
            <button class="text" :disabled="active.config.images.length >= 8" @click="addCarouselImage(active)">添加图片</button>
            <div class="form-grid" style="margin-top: 10px">
              <label class="field"><span>切换间隔（秒）</span><input v-model="active.config.interval" type="number" min="2" max="10" /></label>
              <label class="field"><span>高度（px）</span><input v-model="active.config.height" type="number" min="80" max="600" /></label>
            </div>
          </template>

          <template v-else-if="active.type === 'IMAGE_HOTSPOT'">
            <div class="field">
              <span>底图</span>
              <MediaPicker v-model="active.config.image" kind="IMAGE" hint="建议 750×1000（3:4），≤800KB" />
            </div>
            <div v-for="(hotspot, hotspotIndex) in active.config.hotspots" :key="hotspotIndex" class="deco-subblock">
              <div class="form-grid">
                <label class="field"><span>X %</span><input v-model="hotspot.x" type="number" min="0" max="100" /></label>
                <label class="field"><span>Y %</span><input v-model="hotspot.y" type="number" min="0" max="100" /></label>
                <label class="field"><span>宽 %</span><input v-model="hotspot.w" type="number" min="1" max="100" /></label>
                <label class="field"><span>高 %</span><input v-model="hotspot.h" type="number" min="1" max="100" /></label>
              </div>
              <div class="field">
                <span>跳转</span>
                <LinkTargetEditor v-model="hotspot.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
              </div>
              <button class="danger" @click="active.config.hotspots.splice(hotspotIndex, 1)">移除热区</button>
            </div>
            <button class="text" :disabled="active.config.hotspots.length >= 10" @click="addHotspot(active)">添加热区</button>
          </template>

          <template v-else-if="active.type === 'PRODUCT'">
            <div class="form-grid">
              <label class="field">
                <span>商品来源</span>
                <select v-model="active.config.source">
                  <option value="MANUAL">手动选品</option>
                  <option value="CATEGORY">按类目</option>
                  <option value="MERCHANT">按商户</option>
                </select>
              </label>
              <label class="field">
                <span>布局</span>
                <select v-model="active.config.layout">
                  <option value="GRID">网格</option>
                  <option value="LIST">列表</option>
                </select>
              </label>
              <label class="field"><span>列数</span><input v-model="active.config.columns" type="number" min="2" max="3" /></label>
              <label class="field"><span>数量上限</span><input v-model="active.config.limit" type="number" min="1" max="20" /></label>
            </div>
            <label v-if="active.config.source === 'MANUAL'" class="field">
              <span>选择商品（可多选）</span>
              <select v-model="active.config.product_ids" multiple size="6">
                <option v-for="item in products" :key="item.id" :value="item.id">{{ item.title }}</option>
              </select>
            </label>
            <label v-else-if="active.config.source === 'CATEGORY'" class="field">
              <span>选择类目</span>
              <select v-model="active.config.category_id">
                <option :value="null">请选择…</option>
                <option v-for="item in adminCategories" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
            </label>
            <label v-else class="field">
              <span>选择商户</span>
              <select v-model="active.config.merchant_id">
                <option :value="null">请选择…</option>
                <option v-for="item in merchants" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
            </label>
            <label class="field" style="flex-direction: row; align-items: center; gap: 8px">
              <input v-model="active.config.show_sales" type="checkbox" style="width: auto" />
              <span>显示销量</span>
            </label>
          </template>

          <template v-else-if="active.type === 'SEARCH'">
            <div class="form-grid">
              <label class="field"><span>占位文案</span><input v-model="active.config.placeholder" /></label>
              <label class="field">
                <span>样式</span>
                <select v-model="active.config.style">
                  <option value="DEFAULT">标准</option>
                  <option value="COMPACT">紧凑</option>
                </select>
              </label>
            </div>
            <label class="field">
              <span>热搜词（逗号分隔）</span>
              <input
                :value="(active.config.hot_keywords || []).join('，')"
                @input="active.config.hot_keywords = ($event.target as HTMLInputElement).value.split(/[，,]/).map((v) => v.trim()).filter(Boolean)"
              />
            </label>
          </template>

          <template v-else-if="active.type === 'LOCATION'">
            <div class="form-grid">
              <label class="field"><span>标题</span><input v-model="active.config.title" /></label>
              <label class="field"><span>半径（米）</span><input v-model="active.config.radius" type="number" min="500" max="10000" /></label>
            </div>
          </template>

          <template v-else-if="active.type === 'DIVIDER'">
            <div class="form-grid">
              <label class="field">
                <span>样式</span>
                <select v-model="active.config.style">
                  <option value="BLANK">留白</option>
                  <option value="LINE">细线</option>
                </select>
              </label>
              <label class="field"><span>高度（px）</span><input v-model="active.config.height" type="number" min="1" max="120" /></label>
              <label class="field"><span>颜色</span><input v-model="active.config.color" placeholder="#E3DACB" /></label>
              <label class="field"><span>背景</span><input v-model="active.config.background" placeholder="#F6F1E7" /></label>
            </div>
          </template>

          <template v-else-if="active.type === 'LINK'">
            <div class="form-grid">
              <label class="field"><span>标题</span><input v-model="active.config.title" /></label>
              <label class="field"><span>副标题</span><input v-model="active.config.subtitle" /></label>
              <label class="field">
                <span>样式</span>
                <select v-model="active.config.layout">
                  <option value="CARD">卡片</option>
                  <option value="TEXT">文字</option>
                </select>
              </label>
            </div>
            <div class="field">
              <span>图片（选填）</span>
              <MediaPicker v-model="active.config.image" kind="IMAGE" hint="建议 240×180（4:3），≤200KB" />
            </div>
            <div class="field">
              <span>跳转</span>
              <LinkTargetEditor v-model="active.config.link" :pages="pages" :categories="categories" :merchants="merchants" :products="products" />
            </div>
          </template>
        </div>
        <div v-else class="card">请选择左侧组件以编辑属性</div>
      </aside>
    </div>
  </template>

  <ConfirmDialog
    v-if="leaveConfirm"
    title="返回列表"
    message="返回前请确认草稿已保存；未保存的修改会丢失。"
    confirm-label="返回列表"
    @confirm="router.push('/storefront')"
    @close="leaveConfirm = false"
  />
</template>

<style scoped>
.editor-layout {
  display: grid;
  grid-template-columns: 200px minmax(320px, 1fr) 380px;
  gap: var(--gap-md);
  align-items: start;
}

.editor-column {
  position: sticky;
  top: 16px;
}

.component-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: var(--gap-md);
}

.component-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: var(--fs-table);
}

.component-item.on {
  border-color: var(--brand);
  background: var(--brand-soft);
  color: var(--brand-ink);
}

.component-add {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.phone-frame {
  width: 375px;
  min-height: 620px;
  margin: 0 auto;
  background: #f6f1e7;
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  padding: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-block {
  border-radius: 8px;
  overflow: hidden;
}

.preview-image {
  width: 100%;
  object-fit: cover;
  display: block;
  border-radius: 8px;
  background: #ece3d3;
}

.preview-placeholder,
.preview-empty {
  display: grid;
  place-items: center;
  color: var(--ink-3);
  font-size: var(--fs-help);
  background: #ece3d3;
  border-radius: 8px;
  padding: 12px;
}

.preview-hotspot {
  position: relative;
}

.preview-hotspot-area {
  position: absolute;
  border: 1px dashed rgba(217, 85, 47, 0.8);
  background: rgba(217, 85, 47, 0.12);
}

.preview-products {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.preview-products.list {
  grid-template-columns: 1fr;
}

.preview-product {
  background: #fffdf8;
  border-radius: 8px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--fs-help);
}

.preview-product-cover {
  height: 64px;
  border-radius: 6px;
  background: linear-gradient(150deg, #232f2a, #6b7a55);
  color: #fdf9f0;
  display: grid;
  place-items: center;
  font-size: 18px;
}

.preview-product b {
  color: #d9552f;
}

.preview-search {
  background: #fffdf8;
  border: 1px solid #e3dacb;
  border-radius: 999px;
  padding: 8px 14px;
  color: var(--ink-3);
  font-size: var(--fs-help);
}

.preview-location,
.preview-link {
  background: #fffdf8;
  border: 1px solid #e3dacb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--fs-table);
}

.attr-card {
  max-height: calc(100vh - 140px);
  overflow: auto;
}

@media (max-width: 1400px) {
  .editor-layout {
    grid-template-columns: 180px minmax(300px, 1fr) 340px;
  }
  .phone-frame {
    width: 340px;
  }
}

@media (max-width: 1180px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
  .editor-column {
    position: static;
  }
  .phone-frame {
    width: 375px;
  }
}
</style>
