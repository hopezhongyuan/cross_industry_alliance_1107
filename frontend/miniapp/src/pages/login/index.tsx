import { showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Input, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError } from '../../api'

export default function Login() {
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [debugCode, setDebugCode] = useState('')
  const [accepted, setAccepted] = useState(false)
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
    if (!accepted) {
      setError('请先阅读并同意隐私协议与用户注册协议')
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
      <View className="login-hero">
        <Text className="eyebrow">NEIGHBORHOOD CLUB</Text>
        <Text className="display">把附近的好店，<br />装进你的口袋。</Text>
        <Text className="muted" style={{ display: 'block', marginTop: '14px' }}>
          微信信任登录 · 手机号快捷登录
        </Text>
      </View>

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
        <View style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Input
            className="input"
            name="sms_code"
            type="number"
            placeholder="请输入验证码…"
            value={code}
            onInput={(event) => setCode(event.detail.value)}
          />
          <Button className="link-btn" onClick={sendCode}>获取验证码</Button>
        </View>
        {debugCode && <Text className="muted">Mock 验证码：{debugCode}</Text>}
      </View>

      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="agreement" onClick={() => setAccepted(!accepted)}>
        <View
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '6px',
            border: '1px solid #c9b38d',
            background: accepted ? '#201d19' : '#fffdf8',
            color: '#fdf9f0',
            textAlign: 'center',
            lineHeight: '30px',
            fontSize: '22px',
            flex: '0 0 auto',
          }}
        >
          {accepted ? '✓' : ''}
        </View>
        <Text>
          我已阅读并同意
          <Text className="link-btn" onClick={(event) => { event.stopPropagation(); Taro.navigateTo({ url: '/pages/about/index' }) }}>
            《隐私协议与用户注册协议》
          </Text>
        </Text>
      </View>

      <Button className={`btn ${loading ? 'disabled' : ''}`} onClick={loading ? undefined : login}>
        {loading ? '登录中…' : '登录 / 注册'}
      </Button>
    </View>
  )
}
