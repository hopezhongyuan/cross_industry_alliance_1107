import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type AddressRow } from '../../api'

export default function Addresses() {
  const [items, setItems] = useState<AddressRow[]>([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    receiver_name: '',
    phone: '',
    province: '浙江省',
    city: '杭州市',
    district: '西湖区',
    detail: '',
    is_default: false,
  })
  const [saving, setSaving] = useState(false)

  async function load() {
    try {
      setItems(await api.addresses())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  function update(field: keyof typeof form, value: string | boolean) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function submit() {
    if (!form.receiver_name || !form.phone || !form.detail) {
      setError('请填写收货人、电话与详细地址')
      return
    }
    setSaving(true)
    try {
      await api.createAddress({ ...form, tag: 'HOME' })
      showToast({ title: '已保存', icon: 'success' })
      setShowForm(false)
      setForm((current) => ({ ...current, receiver_name: '', phone: '', detail: '' }))
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function remove(id: number) {
    const result = await Taro.showModal({ title: '删除地址', content: '删除后不可恢复，确认删除吗？' })
    if (!result.confirm) return
    try {
      await api.deleteAddress(id)
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '删除失败')
    }
  }

  return (
    <View className="page">
      <View className="title">收货地址</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {items.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontWeight: 600 }}>{item.receiver_name} {item.phone}</Text>
            {item.is_default && <Text className="tag">默认</Text>}
          </View>
          <View className="muted">{item.province}{item.city}{item.district}{item.detail}</View>
          <View className="row">
            <Button className="link-btn" onClick={() => remove(item.id)}>删除</Button>
          </View>
        </View>
      ))}
      {!items.length && !error && <View className="muted">暂无收货地址</View>}

      {!showForm && (
        <Button className="btn" onClick={() => setShowForm(true)}>新增地址</Button>
      )}
      {showForm && (
        <View className="card">
          <Text className="field-label">收货人</Text>
          <Input className="input" name="receiver_name" placeholder="请输入收货人姓名…" value={form.receiver_name} onInput={(event) => update('receiver_name', event.detail.value)} />
          <Text className="field-label">电话</Text>
          <Input className="input" name="phone" type="number" placeholder="请输入手机号…" value={form.phone} onInput={(event) => update('phone', event.detail.value)} />
          <Text className="field-label">省</Text>
          <Input className="input" name="province" placeholder="请输入省份…" value={form.province} onInput={(event) => update('province', event.detail.value)} />
          <Text className="field-label">市</Text>
          <Input className="input" name="city" placeholder="请输入城市…" value={form.city} onInput={(event) => update('city', event.detail.value)} />
          <Text className="field-label">区县</Text>
          <Input className="input" name="district" placeholder="请输入区县…" value={form.district} onInput={(event) => update('district', event.detail.value)} />
          <Text className="field-label">详细地址</Text>
          <Input className="input" name="detail" placeholder="请输入街道门牌…" value={form.detail} onInput={(event) => update('detail', event.detail.value)} />
          <Button className="rule-btn" onClick={() => update('is_default', !form.is_default)}>
            {form.is_default ? '☑ 设为默认地址' : '☐ 设为默认地址'}
          </Button>
          <Button className={`btn ${saving ? 'disabled' : ''}`} onClick={saving ? undefined : submit}>
            {saving ? '保存中…' : '保存地址'}
          </Button>
          <Button className="btn secondary" onClick={() => setShowForm(false)}>取消</Button>
        </View>
      )}
    </View>
  )
}
