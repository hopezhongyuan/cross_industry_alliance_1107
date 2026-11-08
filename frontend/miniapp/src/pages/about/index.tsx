import { useLoad } from '@tarojs/taro'
import { View, Text, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type PlatformConfigRow } from '../../api'

export default function About() {
  const [config, setConfig] = useState<PlatformConfigRow | null>(null)
  const [error, setError] = useState('')

  useLoad(async () => {
    try {
      setConfig(await api.platformConfig())
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  })

  return (
    <View className="page">
      <View className="title">关于平台与协议</View>
      <View className="card">
        {config?.logo_url ? (
          <Image src={config.logo_url} mode="aspectFit" style={{ width: '96px', height: '96px', marginBottom: '12px' }} />
        ) : null}
        <View className="row"><Text>平台名称</Text><Text>{config?.platform_name || '—'}</Text></View>
        <View className="row"><Text>公司主体</Text><Text>{config?.company_name || '—'}</Text></View>
        <View className="row"><Text>联系电话</Text><Text>{config?.contact_phone || '—'}</Text></View>
        <View className="row"><Text>ICP 备案</Text><Text>{config?.icp_no || '—'}</Text></View>
        <View className="row"><Text>协议版本</Text><Text>{config?.agreement_version || '—'}</Text></View>
      </View>

      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="card">
        <Text style={{ fontSize: '28px', fontWeight: 600 }}>隐私协议</Text>
        <Text style={{ display: 'block', marginTop: '10px', whiteSpace: 'pre-wrap', lineHeight: '1.8' }}>
          {config?.privacy_policy || '平台暂未配置隐私协议。'}
        </Text>
      </View>

      <View className="card">
        <Text style={{ fontSize: '28px', fontWeight: 600 }}>用户注册协议</Text>
        <Text style={{ display: 'block', marginTop: '10px', whiteSpace: 'pre-wrap', lineHeight: '1.8' }}>
          {config?.user_agreement || '平台暂未配置用户注册协议。'}
        </Text>
      </View>
    </View>
  )
}
