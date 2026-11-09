import { useDidShow } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, clearToken, getToken } from '../../api'
import BottomNav from '../../components/BottomNav'

const menus = [
  { label: '我的积分', action: () => Taro.navigateTo({ url: '/pages/points/index' }) },
  { label: '收货地址', action: () => Taro.navigateTo({ url: '/pages/addresses/index' }) },
  { label: '优惠券', hint: 'P1 未开放', action: () => Taro.showToast({ title: 'P1 开放优惠券', icon: 'none' }) },
  { label: '客服与帮助', action: () => Taro.showToast({ title: '客服入口将在正式版开放', icon: 'none' }) },
  { label: '关于平台与协议', action: () => Taro.navigateTo({ url: '/pages/about/index' }) },
  { label: '设置', action: () => Taro.showToast({ title: '设置项将在正式版开放', icon: 'none' }) },
]

const shortcuts = [
  { label: '待接单', status: 'PENDING_ACCEPT' },
  { label: '待履约', status: 'PENDING_FULFILL' },
  { label: '已完成', status: 'COMPLETED' },
]

export default function Me() {
  const [profile, setProfile] = useState<{ nickname: string; phone: string } | null>(null)
  const [points, setPoints] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [loggedIn, setLoggedIn] = useState(Boolean(getToken()))

  useDidShow(() => {
    const hasToken = Boolean(getToken())
    setLoggedIn(hasToken)
    if (!hasToken) {
      setProfile(null)
      setPoints(null)
      return
    }
    api
      .me()
      .then(setProfile)
      .catch((exc) => {
        if (exc instanceof ApiError && exc.status === 401) {
          clearToken()
          setLoggedIn(false)
        }
        setError(exc instanceof ApiError ? exc.message : '加载失败')
      })
    api.pointAccount().then((a) => setPoints(a.balance ?? 0)).catch(() => setPoints(null))
  })

  async function logout() {
    const result = await Taro.showModal({ title: '退出登录', content: '确定退出当前账号吗？' })
    if (!result.confirm) return
    clearToken()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  function openOrders(status = '') {
    Taro.navigateTo({ url: `/pages/orders/index${status ? `?status=${status}` : ''}` })
  }

  return (
    <View className="page">
      <Text className="eyebrow">ACCOUNT</Text>
      <View className="profile-hero">
        <View className="avatar-mark">{profile?.nickname?.slice(0, 1) || '我'}</View>
        {loggedIn ? (
          <View>
            <Text style={{ display: 'block', fontSize: '34px', fontFamily: "'Songti SC', 'Noto Serif SC', serif" }}>
              {profile?.nickname || '邻里会员'}
            </Text>
            <Text className="muted">{profile?.phone || '已登录'}</Text>
            {points !== null && (
              <Text
                className="muted"
                style={{ display: 'block', marginTop: 4, cursor: 'pointer' }}
                onClick={() => Taro.navigateTo({ url: '/pages/points/index' })}
              >
                积分 {points} ›
              </Text>
            )}
          </View>
        ) : (
          <Text style={{ fontSize: '30px' }}>未登录，登录后发现更多好店</Text>
        )}
        <View className="shortcut-row">
          {shortcuts.map((item) => (
            <View key={item.status} className="shortcut" onClick={() => openOrders(item.status)}>
              {item.label}
            </View>
          ))}
          <View className="shortcut" onClick={() => openOrders('')}>全部订单</View>
        </View>
      </View>

      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="card">
        <View className="section-head"><Text>我的服务</Text><Text className="muted">P0</Text></View>
        {menus.map((menu) => (
          <View key={menu.label} className="row" onClick={menu.action}>
            <Text>{menu.label}</Text>
            <Text className="muted">{menu.hint ?? '›'}</Text>
          </View>
        ))}
      </View>

      {!loggedIn && (
        <Button className="btn" onClick={() => Taro.navigateTo({ url: '/pages/login/index' })}>手机号登录</Button>
      )}
      {loggedIn && (
        <Button className="btn secondary" onClick={() => Taro.navigateTo({ url: '/pages/merchant/index' })}>
          进入商户中心
        </Button>
      )}
      {loggedIn && (
        <Button className="btn secondary" onClick={logout}>退出登录</Button>
      )}
      <BottomNav />
    </View>
  )
}
