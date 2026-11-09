import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, clearToken, type Schemas } from '../../../api'
import MerchantHeader from '../../../components/merchant/MerchantHeader'

export default function MerchantSettings() {
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
  const [error, setError] = useState('')

  useLoad(async () => {
    try {
      const p = await api.profile()
      setProfile(p)
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  })

  function formatHours(hours: Record<string, unknown> | undefined): string {
    if (!hours || typeof hours !== 'object') return '-'
    return Object.entries(hours)
      .map(([k, v]) => `${k}: ${v}`)
      .join(' · ')
  }

  async function logout() {
    const result = await Taro.showModal({ title: '退出登录', content: '确定退出当前商户账号？' })
    if (!result.confirm) return
    clearToken()
    showToast({ title: '已退出', icon: 'success' })
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  if (!profile) {
    return (
      <View className="page">
        <View className="title">设置</View>
        {error && <View className="muted">{error}</View>}
      </View>
    )
  }

  return (
    <View className="page">
      <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} statusLabel={profile.status_label} showSettings={false} />
      <View className="title">设置</View>

      <View className="card">
        <View className="mch-setting-row">
          <Text className="mch-setting-label">商户编号</Text>
          <Text className="mch-setting-value">{profile.merchant_no}</Text>
        </View>
        <View className="mch-setting-row">
          <Text className="mch-setting-label">联系电话</Text>
          <Text className="mch-setting-value">{profile.contact_phone || '-'}</Text>
        </View>
        <View className="mch-setting-row">
          <Text className="mch-setting-label">所在地区</Text>
          <Text className="mch-setting-value">
            {[profile.province, profile.city, profile.district].filter(Boolean).join(' ')}
          </Text>
        </View>
        <View className="mch-setting-row">
          <Text className="mch-setting-label">详细地址</Text>
          <Text className="mch-setting-value">{profile.address || '-'}</Text>
        </View>
        <View className="mch-setting-row">
          <Text className="mch-setting-label">营业时间</Text>
          <Text className="mch-setting-value">{formatHours(profile.business_hours)}</Text>
        </View>
      </View>

      <View className="muted" style={{ textAlign: 'center', margin: '16px 0' }}>
        门店信息由平台审核维护，如需修改请联系平台运营
      </View>

      <Button className="btn secondary" onClick={logout}>退出登录</Button>
    </View>
  )
}
