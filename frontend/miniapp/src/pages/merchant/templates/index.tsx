import { useLoad, showToast, showModal, navigateTo } from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type MerchantTemplateRow } from '../../../api'
import { formatMoney } from '../../../format'

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  PENDING_AUDIT: '待审核',
  ON_SALE: '在售',
  OFF_SALE: '已下架',
  REJECTED: '已驳回',
}

const DELIVERY_LABEL: Record<string, string> = {
  EXPRESS: '快递配送',
  PICKUP: '到店自提',
  VERIFY: '到店核销',
  APPOINTMENT: '预约服务',
}

const FILTERS = [
  { value: 'ALL', label: '全部' },
  { value: 'UNCLAIMED', label: '未认领' },
  { value: 'CLAIMED', label: '已认领' },
]

export default function MerchantTemplates() {
  const [items, setItems] = useState<MerchantTemplateRow[]>([])
  const [filter, setFilter] = useState('ALL')
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() {
    try {
      setItems(await api.merchantTemplates())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  async function adopt(item: MerchantTemplateRow, listed: boolean) {
    const result = await showModal({
      title: listed ? '认领并上架' : '认领暂不上架',
      content: `将「${item.title}」认领为本店商品？认领后可自行调整价格库存与上下架。`,
    })
    if (!result.confirm) return
    setBusyId(item.id)
    try {
      await api.adoptTemplate(item.id, listed)
      showToast({ title: '认领成功', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '认领失败')
    } finally {
      setBusyId(null)
    }
  }

  const visible = items.filter((item) => {
    if (filter === 'UNCLAIMED') return !item.adopted_product_id
    if (filter === 'CLAIMED') return Boolean(item.adopted_product_id)
    return true
  })

  return (
    <View className="page">
      <View className="title">平台商品</View>
      <View className="muted">平台发布并分发给本店的商品模板；认领后成为本店商品，可自行上下架。</View>

      {error && (
        <View className="muted" aria-live="polite">
          {error}
        </View>
      )}

      <View style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
        {FILTERS.map((tab) => (
          <Button
            key={tab.value}
            className={`chip ${filter === tab.value ? 'active' : ''}`}
            onClick={() => setFilter(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </View>

      {visible.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '30px' }}>{item.title}</Text>
            {item.adopted_product_id ? (
              <Text className="tag">{STATUS_LABEL[item.adopted_status] ?? '已认领'}</Text>
            ) : (
              <Text className="tag">未认领</Text>
            )}
          </View>
          {item.subtitle ? <Text className="muted">{item.subtitle}</Text> : null}
          <View className="row">
            <Text className="price">{formatMoney(item.price)}</Text>
            <Text className="muted">{item.category_name}</Text>
          </View>
          <Text className="muted">
            {item.skus.length} 个规格 · {item.delivery_types.map((value) => DELIVERY_LABEL[value] ?? value).join(' / ')}
          </Text>
          <View style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
            {item.adopted_product_id ? (
              <Button
                className="chip"
                onClick={() => navigateTo({ url: `/pages/merchant/product-edit/index?id=${item.adopted_product_id}` })}
              >
                管理商品
              </Button>
            ) : (
              <>
                <Button className="chip" disabled={busyId === item.id} onClick={() => adopt(item, true)}>
                  认领并上架
                </Button>
                <Button className="chip" disabled={busyId === item.id} onClick={() => adopt(item, false)}>
                  认领暂不上架
                </Button>
              </>
            )}
          </View>
        </View>
      ))}
      {!visible.length && <View className="muted">暂无平台商品</View>}
    </View>
  )
}
