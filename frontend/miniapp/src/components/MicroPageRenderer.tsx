import Taro from '@tarojs/taro'
import { View, Text, Image, Swiper, SwiperItem, Input, Button } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { api, type DecoComponentRow, type ProductRow, type StoreRow } from '../api'
import { navigateLink } from '../deco/navigate'
import { formatMoney } from '../format'

const DEFAULT_LAT = 30.2741
const DEFAULT_LNG = 120.1551

function ProductCard({ product }: { product: ProductRow }) {
  return (
    <View className="deco-product-card" onClick={() => Taro.navigateTo({ url: `/pages/product/index?id=${product.id}` })}>
      {product.cover_url ? (
        <Image className="deco-product-cover" src={product.cover_url} mode="aspectFill" />
      ) : (
        <View className="deco-product-cover deco-placeholder">商品</View>
      )}
      <Text className="deco-product-title">{product.title}</Text>
      <Text className="price">{formatMoney(product.price)}</Text>
    </View>
  )
}

function ProductBlock({ component }: { component: DecoComponentRow }) {
  const [products, setProducts] = useState<ProductRow[]>([])
  const config = component.config || {}

  useEffect(() => {
    async function load() {
      try {
        const source = config.source || 'MANUAL'
        const result = await api.products(
          source === 'CATEGORY'
            ? { category: Number(config.category_id) }
            : source === 'MERCHANT'
              ? { merchant: Number(config.merchant_id) }
              : {},
        )
        const ids = (config.product_ids || []).map(Number)
        const filtered = source === 'MANUAL' ? result.filter((item) => ids.includes(item.id)) : result
        setProducts(filtered.slice(0, Number(config.limit || 6)))
      } catch (ignored) {
        setProducts([])
      }
    }
    load()
  }, [component.id])

  const columns = Number(config.columns || 2)
  return (
    <View className="deco-section">
      {config.title ? <Text className="deco-section-title">{config.title}</Text> : null}
      <View className={`deco-product-list ${config.layout === 'LIST' ? 'list' : 'grid'}`} style={config.layout === 'LIST' ? {} : { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </View>
      {!products.length ? <Text className="muted">暂无商品</Text> : null}
    </View>
  )
}

function SearchBlock({ component }: { component: DecoComponentRow }) {
  const [keyword, setKeyword] = useState('')
  const [results, setResults] = useState<ProductRow[]>([])
  const config = component.config || {}

  async function search() {
    const query = keyword.trim()
    if (!query) {
      setResults([])
      return
    }
    try {
      setResults((await api.products({ search: query })).slice(0, 6))
    } catch (ignored) {
      setResults([])
    }
  }

  return (
    <View className="deco-section">
      <View className={`deco-search ${config.style === 'COMPACT' ? 'compact' : ''}`}>
        <Input
          className="deco-search-input"
          placeholder={config.placeholder || '搜索商品或门店…'}
          value={keyword}
          onInput={(event) => setKeyword(event.detail.value)}
          onConfirm={search}
        />
        <Button className="deco-search-button" onClick={search}>搜索</Button>
      </View>
      {(config.hot_keywords || []).length ? (
        <View className="deco-hotwords">
          {(config.hot_keywords || []).map((word: string) => (
            <Text key={word} className="tag" onClick={() => { setKeyword(word); }}>
              {word}
            </Text>
          ))}
        </View>
      ) : null}
      {results.length ? (
        <View className="deco-product-list grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
          {results.map((product) => <ProductCard key={product.id} product={product} />)}
        </View>
      ) : null}
    </View>
  )
}

function LocationBlock({ component }: { component: DecoComponentRow }) {
  const [stores, setStores] = useState<StoreRow[]>([])
  const config = component.config || {}

  useEffect(() => {
    api
      .stores({ lat: DEFAULT_LAT, lng: DEFAULT_LNG })
      .then((result) => setStores(result.items.slice(0, 3)))
      .catch(() => setStores([]))
  }, [])

  return (
    <View className="deco-section deco-location">
      <Text className="deco-section-title">{config.title || '附近好店'}</Text>
      <Text className="muted">当前定位：杭州 · 西湖区</Text>
      {stores.map((store) => (
        <View
          key={store.id}
          className="deco-location-item"
          onClick={() => Taro.navigateTo({ url: `/pages/store/index?id=${store.id}` })}
        >
          <Text>{store.name}</Text>
          <Text className="muted">
            {store.distance_meters != null ? `${(store.distance_meters / 1000).toFixed(1)}km` : ''}
          </Text>
        </View>
      ))}
      {!stores.length ? <Text className="muted">附近暂无营业门店</Text> : null}
    </View>
  )
}

export default function MicroPageRenderer({ components }: { components: DecoComponentRow[] }) {
  return (
    <View className="deco-page">
      {components.map((component) => {
        const config = component.config || {}
        if (component.type === 'AD') {
          return (
            <View key={component.id} className="deco-section" onClick={() => navigateLink(config.link, 'push')}>
              <Image
                className="deco-ad"
                src={config.image}
                mode="aspectFill"
                style={{ height: `${Number(config.height || 180)}px` }}
              />
            </View>
          )
        }
        if (component.type === 'CAROUSEL') {
          return (
            <Swiper
              key={component.id}
              className="deco-carousel"
              style={{ height: `${Number(config.height || 220)}px` }}
              autoplay
              interval={Number(config.interval || 4) * 1000}
              indicatorDots={Boolean(config.indicator)}
              circular
            >
              {(config.images || []).map((item: { image: string; link?: { type: string; value: string } }, index: number) => (
                <SwiperItem key={index} onClick={() => navigateLink(item.link, 'push')}>
                  <Image className="deco-carousel-image" src={item.image} mode="aspectFill" />
                </SwiperItem>
              ))}
            </Swiper>
          )
        }
        if (component.type === 'IMAGE_HOTSPOT') {
          return (
            <View key={component.id} className="deco-hotspot">
              <Image className="deco-hotspot-image" src={config.image} mode="widthFix" />
              {(config.hotspots || []).map((hotspot: any, index: number) => (
                <View
                  key={index}
                  className="deco-hotspot-area"
                  style={{
                    left: `${Number(hotspot.x || 0)}%`,
                    top: `${Number(hotspot.y || 0)}%`,
                    width: `${Number(hotspot.w || 0)}%`,
                    height: `${Number(hotspot.h || 0)}%`,
                  }}
                  onClick={() => navigateLink(hotspot.link, 'push')}
                />
              ))}
            </View>
          )
        }
        if (component.type === 'PRODUCT') return <ProductBlock key={component.id} component={component} />
        if (component.type === 'SEARCH') return <SearchBlock key={component.id} component={component} />
        if (component.type === 'LOCATION') return <LocationBlock key={component.id} component={component} />
        if (component.type === 'DIVIDER') {
          return (
            <View
              key={component.id}
              className="deco-divider"
              style={{
                height: `${Number(config.height || 16)}px`,
                background: config.background || 'transparent',
                borderTop: config.style === 'LINE' ? `1px solid ${config.color || '#E3DACB'}` : 'none',
              }}
            />
          )
        }
        if (component.type === 'LINK') {
          return (
            <View key={component.id} className="deco-section" onClick={() => navigateLink(config.link, 'push')}>
              <View className={`deco-link-card ${config.layout === 'TEXT' ? 'text' : ''}`}>
                {config.image ? <Image className="deco-link-image" src={config.image} mode="aspectFill" /> : null}
                <View className="deco-link-body">
                  <Text className="deco-link-title">{config.title}</Text>
                  {config.subtitle ? <Text className="muted">{config.subtitle}</Text> : null}
                </View>
                <Text className="deco-link-arrow">›</Text>
              </View>
            </View>
          )
        }
        return null
      })}
    </View>
  )
}
