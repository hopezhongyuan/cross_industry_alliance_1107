import { useDidShow } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, clearToken, getToken } from '../../api'

const menus = [
  { label: '我的订单', action: () => Taro.switchTab({ url: '/pages/orders/index' }) },
  { label: '收货地址', action: () => Taro.navigateTo({ url: '/pages/addresses/index' }) },
  { label: '优惠券 / 积分', hint: 'P1 未开放', action: () => Taro.showToast({ title: 'P1 开放优惠券与积分', icon: 'none' }) },
  { label: '客服与帮助', action: () => Taro.showToast({ title: '客服入口将在正式版开放', icon: 'none' }) },
  { label: '设置', action: () => Taro.showToast({ title: '设置项将在正式版开放', icon: 'none' }) },
]

export default function Me() {
  const [profile, setProfile] = useState<{ nickname: string; phone: string } | null>(null)
  const [error, setError] = useState('')
  const [loggedIn, setLoggedIn] = useState(Boolean(getToken()))

  useDidShow(() => {
    const hasToken = Boolean(getToken())
    setLoggedIn(hasToken)
    if (!hasToken) {
      setProfile(null)
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
  })

  async function logout() {
    const result = await Taro.showModal({ title: '退出登录', content: '确定退出当前账号吗？' })
    if (!result.confirm) return
    clearToken()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  return (
    <View className="page">
      <View className="title">我的</View>
      <View className="card">
        {loggedIn ? (
          <View>
            <View className="row"><Text>昵称</Text><Text>{profile?.nickname || '—'}</Text></View>
            <View className="row"><Text>手机号</Text><Text>{profile?.phone || '—'}</Text></View>
          </View>
        ) : (
          <View className="muted">未登录</View>
        )}
      </View>

      {loggedIn && (
        <View className="card">
          {menus.map((menu) => (
            <Button key={menu.label} className="rule-btn" onClick={menu.action}>
              <View className="row">
                <Text style={{ color: '#1f2933' }}>{menu.label}</Text>
                <Text className="muted">{menu.hint ?? '›'}</Text>
              </View>
            </Button>
          ))}
        </View>
      )}

      {error && <View className="muted" aria-live="polite">{error}</View>}
      {!loggedIn && (
        <Button className="btn" onClick={() => Taro.navigateTo({ url: '/pages/login/index' })}>去登录</Button>
      )}
      {loggedIn && (
        <Button className="btn secondary" onClick={() => Taro.navigateTo({ url: '/pages/merchant/index' })}>
          商户中心
        </Button>
      )}
      {loggedIn && (
        <Button className="btn secondary" onClick={logout}>退出登录</Button>
      )}
    </View>
  )
}
