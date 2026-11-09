import { showToast } from '@tarojs/taro'
import { View, Input, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { useLoad } from '@tarojs/taro'
import MerchantHeader from '../../../components/merchant/MerchantHeader'

export default function MerchantVerify() {
  const [code, setCode] = useState('')
  const [result, setResult] = useState<{ order_no: string; order_status: string } | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)

  useLoad(async () => {
    try {
      const p = await api.profile()
      setProfile(p)
    } catch { /* ignore */ }
  })

  async function submit() {
    if (!code.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const verified = await api.verifyCode(code.trim())
      setResult(verified)
      showToast({ title: '核销成功', icon: 'success' })
      setCode('')
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '核销失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className="page">
      {profile && <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} showSettings={false} />}
      <View className="title">核销</View>
      <View className="card">
        <Text className="mch-field-label">用户核销码</Text>
        <Input
          className="mch-input"
          placeholder="请输入 6-8 位核销码…"
          value={code}
          onInput={(e) => setCode(e.detail.value)}
        />
        <Button className={`btn ${loading ? 'disabled' : ''}`} style={{ marginTop: 16 }} onClick={loading ? undefined : submit}>
          {loading ? '核销中…' : '确认核销'}
        </Button>
      </View>
      {error && <View className="muted" style={{ marginTop: 12 }}>{error}</View>}
      {result && (
        <View className="card">
          <View className="row"><Text>订单号</Text><Text>{result.order_no}</Text></View>
          <View className="row"><Text>订单状态</Text><Text className="tag">{result.order_status}</Text></View>
        </View>
      )}
    </View>
  )
}
