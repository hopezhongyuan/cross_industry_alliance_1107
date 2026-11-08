import Taro from '@tarojs/taro'
import { View, Text, Image } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { api, type StoreNavItemRow } from '../api'
import { linkPath, navigateLink } from '../deco/navigate'

const DEFAULT_NAV: StoreNavItemRow[] = [
  { id: -1, title: '首页', icon_selected: '', icon_unselected: '', link_type: 'FUNCTION', link_value: 'HOME', sort: 0, status: 'ENABLED' },
  { id: -2, title: '购物车', icon_selected: '', icon_unselected: '', link_type: 'FUNCTION', link_value: 'CART', sort: 1, status: 'ENABLED' },
  { id: -3, title: '订单', icon_selected: '', icon_unselected: '', link_type: 'FUNCTION', link_value: 'ORDERS', sort: 2, status: 'ENABLED' },
  { id: -4, title: '我的', icon_selected: '', icon_unselected: '', link_type: 'FUNCTION', link_value: 'ME', sort: 3, status: 'ENABLED' },
]

let navCache: StoreNavItemRow[] | null = null

function normalizePath(path?: string): string {
  return (path || '').replace(/^\//, '')
}

export default function BottomNav() {
  const [items, setItems] = useState<StoreNavItemRow[]>(navCache ?? DEFAULT_NAV)
  const router = Taro.getCurrentInstance().router
  const currentPath = normalizePath(router?.path)
  const currentSlug = router?.params?.slug || ''

  useEffect(() => {
    if (navCache) return
    api
      .storeNav()
      .then((result) => {
        if (result.length) {
          navCache = result
          setItems(result)
        }
      })
      .catch(() => {
        navCache = DEFAULT_NAV
      })
  }, [])

  function isActive(item: StoreNavItemRow): boolean {
    if (item.link_type === 'MICRO_PAGE') {
      return currentPath === 'pages/micro/index' && currentSlug === item.link_value
    }
    if (item.link_type !== 'FUNCTION') return false
    return currentPath === normalizePath(linkPath({ type: item.link_type, value: item.link_value }))
  }

  function select(item: StoreNavItemRow) {
    if (isActive(item)) return
    const mode = item.link_type === 'FUNCTION' || item.link_type === 'MICRO_PAGE' ? 'tab' : 'push'
    navigateLink({ type: item.link_type, value: item.link_value }, mode)
  }

  return (
    <View>
      <View className="bottom-nav-spacer" />
      <View className="bottom-nav">
        {items.map((item) => {
          const active = isActive(item)
          const icon = active ? item.icon_selected : item.icon_unselected
          return (
            <View key={item.id} className={`bottom-nav-item ${active ? 'active' : ''}`} onClick={() => select(item)}>
              {icon ? (
                <Image className="bottom-nav-icon" src={icon} mode="aspectFit" />
              ) : (
                <Text className="bottom-nav-fallback">{item.title.slice(0, 1)}</Text>
              )}
              <Text className="bottom-nav-label">{item.title}</Text>
            </View>
          )
        })}
      </View>
    </View>
  )
}
