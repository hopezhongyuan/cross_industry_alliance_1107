import { useLoad, showToast, showModal } from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type MerchantProductCategoryRow } from '../../../api'

export default function MerchantCategories() {
  const [categories, setCategories] = useState<MerchantProductCategoryRow[]>([])
  const [name, setName] = useState('')
  const [sort, setSort] = useState('0')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    try {
      setCategories(await api.merchantProductCategories())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  function edit(item: MerchantProductCategoryRow) {
    setEditingId(item.id)
    setName(item.name)
    setSort(String(item.sort))
    setError('')
  }

  function reset() {
    setEditingId(null)
    setName('')
    setSort('0')
    setError('')
  }

  async function save() {
    if (!name.trim()) {
      setError('请填写分类名称')
      return
    }
    setSaving(true)
    try {
      const payload = { name: name.trim(), sort: Number(sort || 0) }
      if (editingId) {
        await api.updateMerchantProductCategory(editingId, payload)
        showToast({ title: '已保存', icon: 'success' })
      } else {
        await api.createMerchantProductCategory(payload)
        showToast({ title: '已新增', icon: 'success' })
      }
      reset()
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function remove(item: MerchantProductCategoryRow) {
    const result = await showModal({ title: '删除分类', content: `确定删除「${item.name}」吗？` })
    if (!result.confirm) return
    try {
      await api.deleteMerchantProductCategory(item.id)
      showToast({ title: '已删除', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '删除失败')
    }
  }

  return (
    <View className="page">
      <View className="title">商品分类</View>
      <View className="muted">仅本店可见，一级分类；与平台商品类目互不影响。</View>

      {error && (
        <View className="muted" aria-live="polite">
          {error}
        </View>
      )}

      <View className="card">
        <Text className="field-label">{editingId ? '编辑分类' : '新增分类'}</Text>
        <Input
          className="input"
          name="category_name"
          placeholder="分类名称，如：本店热销…"
          value={name}
          onInput={(event) => setName(event.detail.value)}
        />
        <Input
          className="input"
          name="category_sort"
          type="number"
          placeholder="排序，数字越小越靠前…"
          value={sort}
          onInput={(event) => setSort(event.detail.value)}
        />
        <View style={{ display: 'flex', gap: '12px' }}>
          <Button className="btn" style={{ marginTop: 0 }} disabled={saving} onClick={save}>
            {saving ? '保存中…' : editingId ? '保存修改' : '新增分类'}
          </Button>
          {editingId && (
            <Button className="chip" onClick={reset}>
              取消编辑
            </Button>
          )}
        </View>
      </View>

      {categories.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '30px' }}>{item.name}</Text>
            <Text className="tag">{item.status === 'ENABLED' ? '启用' : '停用'}</Text>
          </View>
          <View className="row">
            <Text className="muted">排序 {item.sort}</Text>
            <Text className="muted">商品 {item.product_count} 件</Text>
          </View>
          <View style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
            <Button className="chip" onClick={() => edit(item)}>
              编辑
            </Button>
            <Button className="chip" onClick={() => remove(item)}>
              删除
            </Button>
          </View>
        </View>
      ))}
      {!categories.length && <View className="muted">暂无分类，先新增一个吧</View>}
    </View>
  )
}
