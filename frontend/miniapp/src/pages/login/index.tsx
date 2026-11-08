import { showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Input, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError } from '../../api'

export default function Login() {
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [debugCode, setDebugCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function sendCode() {
    if (!phone) {
      setError('请输入手机号')
      return
    }
    try {
      const result = await api.sendSms(phone)
      setDebugCode(result.debug_code ?? '')
      showToast({ title: '验证码已发送', icon: 'success' })
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '发送失败')
    }
  }

  async function login() {
    if (!phone || !code) {
      setError('请输入手机号与验证码')
      return
    }
    setLoading(true)
    setError('')
    try {
      await api.loginSms(phone, code)
      showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => Taro.navigateBack(), 600)
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className="page">
      <View className="title">手机号登录</View>
      <View className="card">
        <Text className="field-label">手机号</Text>
        <Input
          className="input"
          name="phone"
          type="number"
          placeholder="请输入手机号…"
          value={phone}
          onInput={(event) => setPhone(event.detail.value)}
        />
        <Text className="field-label">验证码</Text>
        <Input
          className="input"
          name="sms_code"
          type="number"
          placeholder="请输入验证码…"
          value={code}
          onInput={(event) => setCode(event.detail.value)}
        />
        <Button className="link-btn" onClick={sendCode}>获取验证码</Button>
        {debugCode && <Text className="muted">Mock 验证码：{debugCode}</Text>}
      </View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      <Button className={`btn ${loading ? 'disabled' : ''}`} onClick={loading ? undefined : login}>
        {loading ? '登录中…' : '登录'}
      </Button>
    </View>
  )
}
