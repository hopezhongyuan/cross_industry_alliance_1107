import { useDidShow } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, clearToken, getToken } from '../../api'

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
      {error && <View className="muted">{error}</View>}
      {!loggedIn && (
        <View className="btn" onClick={() => Taro.navigateTo({ url: '/pages/login/index' })}>去登录</View>
      )}
      {loggedIn && (
        <View className="btn secondary" onClick={() => Taro.navigateTo({ url: '/pages/merchant/index' })}>
          商户中心
        </View>
      )}
      {loggedIn && (
        <View
          className="btn secondary"
          onClick={() => {
            clearToken()
            Taro.reLaunch({ url: '/pages/index/index' })
          }}
        >
          退出登录
        </View>
      )}
    </View>
  )
}
