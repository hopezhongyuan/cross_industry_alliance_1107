import { useLoad, useRouter } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CategoryRow, type ProductRow } from '../../api'
import BottomNav from '../../components/BottomNav'
import { formatMoney } from '../../format'

export default function CategoryPage() {
  const router = useRouter()
  const initialCategory = Number(router.params.category || 0)
  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [products, setProducts] = useState<ProductRow[]>([])
  const [parentId, setParentId] = useState<number | null>(initialCategory || null)
  const [childId, setChildId] = useState<number | null>(null)
  const [error, setError] = useState('')

  const parents = categories.filter((item) => !item.parent)
  const children = categories.filter((item) => item.parent === parentId)

  async function loadProducts(categoryId: number | null) {
    try {
      setProducts(await api.products({ category: categoryId || undefined }))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(async () => {
    try {
      const list = await api.categories()
      setCategories(list)
      const firstParent = initialCategory || list.find((item) => !item.parent)?.id || null
      setParentId(firstParent)
      const firstChild = list.find((item) => item.parent === firstParent)
      setChildId(firstChild?.id ?? null)
      await loadProducts(firstChild?.id ?? firstParent)
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  })

  async function pickParent(id: number) {
    setParentId(id)
    const child = categories.find((item) => item.parent === id)
    setChildId(child?.id ?? null)
    await loadProducts(child?.id ?? id)
  }

  async function pickChild(id: number) {
    setChildId(id)
    await loadProducts(id)
  }

  return (
    <View className="page deco-page-shell" style={{ paddingBottom: '80px' }}>
      <View style={{ padding: '24px 24px 0' }}>
        <Text className="eyebrow">DISCOVER</Text>
        <View className="title">商品分类</View>
      </View>
      {error && <View className="muted" style={{ padding: '0 24px' }}>{error}</View>}

      <View className="category-layout">
        <View className="category-rail">
          {parents.map((item) => (
            <View
              key={item.id}
              className={`category-rail-item ${parentId === item.id ? 'active' : ''}`}
              onClick={() => pickParent(item.id)}
            >
              {item.name}
            </View>
          ))}
        </View>
        <View className="category-main">
          {children.length > 0 ? (
            <View className="sku-row" style={{ marginBottom: '16px' }}>
              {children.map((item) => (
                <View
                  key={item.id}
                  className={`sku-chip ${childId === item.id ? 'active' : ''}`}
                  onClick={() => pickChild(item.id)}
                >
                  {item.name}
                </View>
              ))}
            </View>
          ) : null}
          <View className="deco-product-list grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
            {products.map((product) => (
              <View
                key={product.id}
                className="deco-product-card"
                onClick={() => Taro.navigateTo({ url: `/pages/product/index?id=${product.id}` })}
              >
                {product.cover_url ? (
                  <Image className="deco-product-cover" src={product.cover_url} mode="aspectFill" />
                ) : (
                  <View className="deco-product-cover deco-placeholder">{product.title.slice(0, 1)}</View>
                )}
                <Text className="deco-product-title">{product.title}</Text>
                <Text className="price">{formatMoney(product.price)}</Text>
              </View>
            ))}
          </View>
          {!products.length ? <View className="muted">该分类暂无商品</View> : null}
        </View>
      </View>
      <BottomNav />
    </View>
  )
}
