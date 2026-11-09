import { useLoad, showToast } from '@tarojs/taro'
import { View, Text, Input, Button, Picker } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { formatMoney, formatDate } from '../../../format'

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  ACTIVE: '进行中',
  PAUSED: '已暂停',
  EXPIRED: '已过期',
}

const SCOPE_OPTIONS = [
  { value: 'ALL', label: '全部商品' },
  { value: 'CATEGORY', label: '指定类目' },
  { value: 'PRODUCT', label: '指定商品' },
]

export default function MerchantCoupons() {
  const [coupons, setCoupons] = useState<Schemas['Coupon'][]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  // 表单
  const [name, setName] = useState('')
  const [faceValue, setFaceValue] = useState('')
  const [minAmount, setMinAmount] = useState('0')
  const [scopeType, setScopeType] = useState<'ALL' | 'CATEGORY' | 'PRODUCT'>('ALL')
  const [totalStock, setTotalStock] = useState('0')
  const [perUserLimit, setPerUserLimit] = useState('1')
  const [validFrom, setValidFrom] = useState('')
  const [validTo, setValidTo] = useState('')
  const [description, setDescription] = useState('')

  async function load() {
    try {
      setCoupons(await api.merchantCoupons())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  function resetForm() {
    setName('')
    setFaceValue('')
    setMinAmount('0')
    setScopeType('ALL')
    setTotalStock('0')
    setPerUserLimit('1')
    setValidFrom('')
    setValidTo('')
    setDescription('')
  }

  async function create() {
    if (!name.trim()) return setError('请填写券名称')
    const face = Math.round(Number(faceValue) * 100)
    if (!face || face <= 0) return setError('请填写正确的面额（元）')
    if (!validFrom || !validTo) return setError('请选择有效期')
    setSaving(true)
    setError('')
    try {
      await api.createMerchantCoupon({
        name: name.trim(),
        face_value: face,
        min_amount: Math.round(Number(minAmount || 0) * 100),
        scope_type: scopeType,
        scope_category_ids: [],
        scope_product_ids: [],
        total_stock: Number(totalStock || 0),
        per_user_limit: Number(perUserLimit || 1),
        valid_from: new Date(validFrom).toISOString(),
        valid_to: new Date(validTo).toISOString(),
        description: description.trim(),
      })
      showToast({ title: '已创建', icon: 'success' })
      resetForm()
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '创建失败')
    } finally {
      setSaving(false)
    }
  }

  async function toggleStatus(coupon: Schemas['Coupon']) {
    if (!coupon.id) return
    const action = coupon.status === 'ACTIVE' ? 'pause' : 'activate'
    try {
      await api.merchantCouponStatus(coupon.id, action)
      showToast({ title: action === 'pause' ? '已暂停' : '已启用', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '操作失败')
    }
  }

  return (
    <View className="page">
      <View className="title">优惠券管理</View>
      <View className="muted">商户券成本由本店承担，仅限本店商品使用。</View>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      <View className="card">
        <Text className="field-label">新增商户券</Text>
        <Input className="input" placeholder="券名称，如：新客立减 10 元" value={name} onInput={(e) => setName(e.detail.value)} />
        <View style={{ display: 'flex', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text className="field-label">面额（元）</Text>
            <Input className="input" type="digit" placeholder="10" value={faceValue} onInput={(e) => setFaceValue(e.detail.value)} />
          </View>
          <View style={{ flex: 1 }}>
            <Text className="field-label">满减门槛（元）</Text>
            <Input className="input" type="digit" placeholder="0=无门槛" value={minAmount} onInput={(e) => setMinAmount(e.detail.value)} />
          </View>
        </View>
        <Text className="field-label">适用范围</Text>
        <Picker
          mode="selector"
          range={SCOPE_OPTIONS.map((o) => o.label)}
          onChange={(e) => setScopeType(SCOPE_OPTIONS[Number(e.detail.value)].value as 'ALL' | 'CATEGORY' | 'PRODUCT')}
        >
          <View className="input" style={{ lineHeight: '80px' }}>
            {SCOPE_OPTIONS.find((o) => o.value === scopeType)?.label}
          </View>
        </Picker>
        <View style={{ display: 'flex', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text className="field-label">发放总量（0=不限）</Text>
            <Input className="input" type="number" value={totalStock} onInput={(e) => setTotalStock(e.detail.value)} />
          </View>
          <View style={{ flex: 1 }}>
            <Text className="field-label">每人限领</Text>
            <Input className="input" type="number" value={perUserLimit} onInput={(e) => setPerUserLimit(e.detail.value)} />
          </View>
        </View>
        <View style={{ display: 'flex', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text className="field-label">生效时间</Text>
            <Input className="input" type="text" placeholder="2025-01-01 00:00" value={validFrom} onInput={(e) => setValidFrom(e.detail.value)} />
          </View>
          <View style={{ flex: 1 }}>
            <Text className="field-label">失效时间</Text>
            <Input className="input" type="text" placeholder="2025-12-31 23:59" value={validTo} onInput={(e) => setValidTo(e.detail.value)} />
          </View>
        </View>
        <Input className="input" placeholder="使用说明（可选）" value={description} onInput={(e) => setDescription(e.detail.value)} />
        <Button className="btn" disabled={saving} onClick={create}>
          {saving ? '创建中…' : '创建优惠券'}
        </Button>
      </View>

      {coupons.map((c) => (
        <View key={c.id} className="card">
          <View className="row">
            <Text style={{ fontSize: 30, fontWeight: 600 }}>{c.name}</Text>
            <Text className="tag">{STATUS_LABEL[c.status ?? ''] ?? c.status}</Text>
          </View>
          <View className="row">
            <Text className="muted">面额 {formatMoney(c.face_value)}</Text>
            <Text className="muted">{(c.min_amount ?? 0) > 0 ? `满${formatMoney(c.min_amount)}可用` : '无门槛'}</Text>
          </View>
          <View className="row">
            <Text className="muted">已领 {c.issued_count ?? 0}{c.total_stock ? `/${c.total_stock}` : ''}</Text>
            <Text className="muted">每人限 {c.per_user_limit}</Text>
          </View>
          <View className="row">
            <Text className="muted">{formatDate(c.valid_from)} ~ {formatDate(c.valid_to)}</Text>
          </View>
          {(c.status === 'ACTIVE' || c.status === 'PAUSED' || c.status === 'DRAFT') && (
            <View style={{ display: 'flex', gap: 12, marginTop: 10 }}>
              <Button className="chip" onClick={() => toggleStatus(c)}>
                {c.status === 'ACTIVE' ? '暂停' : '启用'}
              </Button>
            </View>
          )}
        </View>
      ))}
      {!coupons.length && <View className="muted">暂无优惠券</View>}
    </View>
  )
}
