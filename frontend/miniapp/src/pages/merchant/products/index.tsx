import { useLoad, showToast, navigateTo } from '@tarojs/taro'
import { View, Text, Button, Input } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type MerchantProductRow } from '../../../api'
import { formatMoney } from '../../../format'

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  PENDING_AUDIT: '待审核',
  ON_SALE: '在售',
  OFF_SALE: '已下架',
  REJECTED: '已驳回',
}

const TABS = [
  { value: '', label: '全部' },
  { value: 'PENDING_AUDIT', label: '待审核' },
  { value: 'ON_SALE', label: '在售' },
  { value: 'OFF_SALE', label: '已下架' },
  { value: 'REJECTED', label: '已驳回' },
]

export default function MerchantProducts() {
  const [items, setItems] = useState<MerchantProductRow[]>([])
  const [status, setStatus] = useState('')
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function load(nextStatus = status, nextKeyword = keyword) {
    try {
      setStatus(nextStatus)
      const result = await api.merchantProducts(nextStatus, nextKeyword)
      setItems(result.items)
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(() => load(''))

  function openEdit(id?: number) {
    navigateTo({ url: `/pages/merchant/product-edit/index${id ? `?id=${id}` : ''}` })
  }

  async function toggleSale(item: MerchantProductRow) {
    const target = item.status === 'ON_SALE' ? 'OFF_SALE' : 'ON_SALE'
    setBusy(true)
    try {
      await api.setMerchantProductStatus(item.id, target)
      showToast({ title: target === 'OFF_SALE' ? '已下架' : '已上架', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <View className="page">
      <View className="title">商品管理</View>
      <View style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
        <Input
          className="input"
          name="q"
          placeholder="搜索商品标题…"
          value={keyword}
          onInput={(event) => setKeyword(event.detail.value)}
        />
        <Button className="btn" style={{ width: '120px', marginTop: 0 }} onClick={() => load(status, keyword)}>
          搜索
        </Button>
      </View>

      <View style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
        {TABS.map((tab) => (
          <Button
            key={tab.value || 'ALL'}
            className={`chip ${status === tab.value ? 'active' : ''}`}
            onClick={() => load(tab.value, keyword)}
          >
            {tab.label}
          </Button>
        ))}
      </View>

      <Button className="btn" style={{ marginTop: 0, marginBottom: '16px' }} onClick={() => openEdit()}>
        发布商品
      </Button>

      {error && (
        <View className="muted" aria-live="polite">
          {error}
        </View>
      )}

      {items.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '30px' }}>{item.title}</Text>
            <Text className="tag">{STATUS_LABEL[item.status] ?? item.status}</Text>
          </View>
          <View className="row">
            <Text className="price">{formatMoney(item.price)}</Text>
            <Text className="muted">
              库存 {item.total_stock} · 已售 {item.sold_count}
            </Text>
          </View>
          {item.reject_reason ? <Text className="muted">驳回原因：{item.reject_reason}</Text> : null}
          {item.off_sale_by === 'PLATFORM' ? (
            <Text className="muted">平台下架：{item.off_sale_reason || '违规下架'}</Text>
          ) : null}
          {(item.product_code || item.merchant_category_name) && (
            <Text className="muted">
              {item.product_code ? `货号 ${item.product_code}` : ''}
              {item.product_code && item.merchant_category_name ? ' · ' : ''}
              {item.merchant_category_name}
            </Text>
          )}
          <View style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
            {item.status !== 'PENDING_AUDIT' && (
              <Button className="chip" onClick={() => openEdit(item.id)}>
                编辑
              </Button>
            )}
            {(item.status === 'ON_SALE' || (item.status === 'OFF_SALE' && item.off_sale_by !== 'PLATFORM')) && (
              <Button className="chip" disabled={busy} onClick={() => toggleSale(item)}>
                {item.status === 'ON_SALE' ? '下架' : '上架'}
              </Button>
            )}
          </View>
        </View>
      ))}
      {!items.length && <View className="muted">暂无商品</View>}
    </View>
  )
}
