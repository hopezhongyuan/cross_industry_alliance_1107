import { useLoad, showToast, navigateTo } from '@tarojs/taro'
import { View, Text, Button, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type MerchantProductRow, type Schemas } from '../../../api'
import { formatMoney } from '../../../format'
import MerchantHeader from '../../../components/merchant/MerchantHeader'
import SearchBar from '../../../components/merchant/SearchBar'
import StatusBadge from '../../../components/merchant/StatusBadge'
import EmptyState from '../../../components/merchant/EmptyState'

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
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
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

  useLoad(async () => {
    try {
      const p = await api.profile()
      setProfile(p)
    } catch { /* ignore */ }
    load('')
  })

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
      {profile && <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} showSettings={false} />}
      <View className="title">商品管理</View>

      <SearchBar value={keyword} placeholder="搜索商品标题…" onChange={setKeyword} onSearch={() => load(status, keyword)} />

      <View className="mch-tabs">
        {TABS.map((tab) => (
          <Button
            key={tab.value || 'ALL'}
            className={`mch-tab ${status === tab.value ? 'active' : ''}`}
            onClick={() => load(tab.value, keyword)}
          >
            {tab.label}
          </Button>
        ))}
      </View>

      <Button className="btn" style={{ marginBottom: 16 }} onClick={() => openEdit()}>发布商品</Button>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      {items.length > 0 ? items.map((item) => (
        <View key={item.id} className="card">
          <View className="row" style={{ alignItems: 'flex-start' }}>
            {item.cover_url ? (
              <Image src={item.cover_url} style={{ width: 100, height: 100, borderRadius: 10, flex: '0 0 auto' }} mode="aspectFill" />
            ) : (
              <View style={{ width: 100, height: 100, borderRadius: 10, background: '#f1eadc', flex: '0 0 auto' }} />
            )}
            <View style={{ flex: 1, marginLeft: 14, minWidth: 0 }}>
              <View className="row" style={{ padding: 0 }}>
                <Text style={{ fontSize: '28px', fontWeight: 500, flex: 1 }}>{item.title}</Text>
                <StatusBadge kind="product" status={item.status} />
              </View>
              <View className="row" style={{ padding: '8px 0 0' }}>
                <Text className="price">{formatMoney(item.price)}</Text>
                <Text className="muted">库存 {item.total_stock} · 已售 {item.sold_count}</Text>
              </View>
              {item.reject_reason ? <Text className="muted">驳回：{item.reject_reason}</Text> : null}
              {item.off_sale_by === 'PLATFORM' ? (
                <Text className="muted">平台下架：{item.off_sale_reason || '违规下架'}</Text>
              ) : null}
            </View>
          </View>
          <View className="mch-actions">
            {item.status !== 'PENDING_AUDIT' && (
              <Button className="chip" onClick={() => openEdit(item.id)}>编辑</Button>
            )}
            {(item.status === 'ON_SALE' || (item.status === 'OFF_SALE' && item.off_sale_by !== 'PLATFORM')) && (
              <Button className="chip" disabled={busy} onClick={() => toggleSale(item)}>
                {item.status === 'ON_SALE' ? '下架' : '上架'}
              </Button>
            )}
          </View>
        </View>
      )) : (
        <EmptyState text="暂无商品" icon="📦" />
      )}
    </View>
  )
}
