import { useLoad, showToast, navigateBack, useRouter } from '@tarojs/taro'
import { View, Text, Input, Button, Picker, Textarea } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CategoryRow, type MerchantProductCategoryRow, type MerchantProductPayload } from '../../../api'

const DELIVERY_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  PHYSICAL: [
    { value: 'EXPRESS', label: '快递配送' },
    { value: 'STORE_DELIVERY', label: '门店配送' },
    { value: 'PICKUP', label: '到店自提' },
  ],
  SERVICE: [
    { value: 'VERIFY', label: '到店核销' },
    { value: 'APPOINTMENT', label: '预约服务' },
  ],
  COUPON: [{ value: 'VERIFY', label: '到店核销' }],
}

const WEEKDAY_OPTIONS = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' },
]

type SkuForm = { sku_code: string; spec_name: string; price: string; stock: string }

export default function MerchantProductEdit() {
  const router = useRouter()
  const productId = Number(router.params.id ?? 0)

  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [merchantCategories, setMerchantCategories] = useState<MerchantProductCategoryRow[]>([])
  const [form, setForm] = useState({
    type: 'PHYSICAL',
    category_id: '',
    merchant_category_id: '',
    product_code: '',
    title: '',
    subtitle: '',
    cover_url: '',
    description: '',
    price: '',
    original_price: '',
    verify_days: '30',
    appointment_required: false,
    acceptance_required: true,
    valid_type: 'DAYS' as 'DAYS' | 'PERMANENT' | 'RANGE',
    valid_days: '7',
    valid_from: '',
    valid_to: '',
    usable_weekdays: [] as number[],
    exclude_holidays: false,
    verify_count: '1',
    delivery_types: ['EXPRESS'],
  })
  const [skus, setSkus] = useState<SkuForm[]>([{ sku_code: 'DEFAULT', spec_name: '默认规格', price: '', stock: '0' }])
  const [version, setVersion] = useState<number | null>(null)
  const [productStatus, setProductStatus] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useLoad(async () => {
    try {
      const [list, ownCategories] = await Promise.all([api.categories(), api.merchantProductCategories()])
      setCategories(list)
      setMerchantCategories(ownCategories)
      if (productId) {
        const product = await api.merchantProduct(productId)
        setVersion(product.version)
        setProductStatus(product.status)
        setForm({
          type: product.type,
          category_id: String(product.category_id ?? ''),
          merchant_category_id: String(product.merchant_category_id ?? ''),
          product_code: product.product_code,
          title: product.title,
          subtitle: product.subtitle,
          cover_url: product.cover_url,
          description: product.description,
          price: String(product.price / 100),
          original_price: String(product.original_price / 100),
          verify_days: String(product.verify_days),
          appointment_required: product.appointment_required,
          acceptance_required: product.acceptance_required ?? true,
          valid_type: product.valid_type ?? 'DAYS',
          valid_days: String(product.valid_days ?? 7),
          valid_from: product.valid_from ?? '',
          valid_to: product.valid_to ?? '',
          usable_weekdays: product.usable_weekdays ?? [],
          exclude_holidays: product.exclude_holidays ?? false,
          verify_count: String(product.verify_count ?? 1),
          delivery_types: product.delivery_types,
        })
        setSkus(
          product.skus.map((sku) => ({
            sku_code: sku.sku_code,
            spec_name: String((sku.spec_json as { name?: string }).name ?? ''),
            price: String(sku.price / 100),
            stock: String(sku.stock),
          })),
        )
      }
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载失败')
    }
  })

  function patch(values: Partial<typeof form>) {
    setForm((current) => ({ ...current, ...values }))
  }

  function changeType(value: 'PHYSICAL' | 'SERVICE' | 'COUPON') {
    patch({
      type: value,
      delivery_types: [DELIVERY_OPTIONS[value][0].value],
      appointment_required: false,
      acceptance_required: value === 'PHYSICAL' ? form.acceptance_required : true,
    })
  }

  function toggleWeekday(value: number) {
    const next = form.usable_weekdays.includes(value)
      ? form.usable_weekdays.filter((item) => item !== value)
      : [...form.usable_weekdays, value].sort((a, b) => a - b)
    patch({ usable_weekdays: next })
  }

  function toggleDelivery(value: string) {
    const next = form.delivery_types.includes(value)
      ? form.delivery_types.filter((item) => item !== value)
      : [...form.delivery_types, value]
    patch({
      delivery_types: next,
      appointment_required: next.includes('APPOINTMENT') ? form.appointment_required : false,
    })
  }

  function updateSku(index: number, values: Partial<SkuForm>) {
    setSkus((current) => current.map((sku, idx) => (idx === index ? { ...sku, ...values } : sku)))
  }

  function addSku() {
    setSkus((current) => [...current, { sku_code: '', spec_name: '', price: '', stock: '0' }])
  }

  function removeSku(index: number) {
    setSkus((current) => current.filter((_, idx) => idx !== index))
  }

  function yuanToFen(value: string): number {
    return Math.round(Number(value || 0) * 100)
  }

  async function submit() {
    setError('')
    if (!form.title.trim()) return setError('请填写商品标题')
    if (!form.category_id) return setError('请选择类目')
    if (!form.delivery_types.length) return setError('请选择履约方式')
    const priceAmount = yuanToFen(form.price)
    if (priceAmount < 1) return setError('请填写正确的售价')
    const codes = skus.map((sku) => sku.sku_code.trim())
    if (skus.length === 0 || codes.some((code) => !code)) return setError('请填写完整 SKU 编码')
    if (new Set(codes).size !== codes.length) return setError('SKU 编码重复')
    const skuPayload = skus.map((sku) => ({
      sku_code: sku.sku_code.trim(),
      spec: sku.spec_name.trim() ? { name: sku.spec_name.trim() } : {},
      price_amount: yuanToFen(sku.price),
      stock: Number(sku.stock || 0),
    }))
    if (skuPayload.some((sku) => sku.price_amount < 1)) return setError('SKU 售价必须大于 0')
    if (skuPayload.some((sku) => !Number.isInteger(sku.stock) || sku.stock < 0)) {
      return setError('SKU 库存必须为非负整数')
    }
    if (form.type === 'COUPON') {
      if (form.valid_type === 'DAYS' && Number(form.valid_days || 0) < 1) {
        return setError('请填写卡券有效天数')
      }
      if (form.valid_type === 'RANGE' && (!form.valid_from || !form.valid_to)) {
        return setError('请选择卡券生效与失效时间')
      }
      const count = Number(form.verify_count || 0)
      if (!Number.isInteger(count) || count < 1) return setError('核销次数必须大于 0')
    }

    const payload: MerchantProductPayload = {
      category_id: Number(form.category_id),
      merchant_category_id: form.merchant_category_id ? Number(form.merchant_category_id) : null,
      product_code: form.product_code.trim(),
      type: form.type as 'PHYSICAL' | 'SERVICE' | 'COUPON',
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      cover_url: form.cover_url.trim(),
      description: form.description.trim(),
      price_amount: priceAmount,
      original_price_amount: yuanToFen(form.original_price),
      verify_days: Number(form.verify_days || 30),
      appointment_required: form.appointment_required,
      acceptance_required: form.type === 'PHYSICAL' ? form.acceptance_required : true,
      delivery_types: form.delivery_types,
      skus: skuPayload,
    }
    if (form.type === 'COUPON') {
      payload.valid_type = form.valid_type
      payload.valid_days = form.valid_type === 'DAYS' ? Number(form.valid_days || 1) : null
      payload.valid_from = form.valid_type === 'RANGE' ? new Date(form.valid_from).toISOString() : null
      payload.valid_to = form.valid_type === 'RANGE' ? new Date(form.valid_to).toISOString() : null
      payload.usable_weekdays = form.usable_weekdays
      payload.exclude_holidays = form.exclude_holidays
      payload.verify_count = Number(form.verify_count || 1)
    }

    setSaving(true)
    try {
      if (version !== null && productId) {
        await api.updateMerchantProduct(productId, { ...payload, version })
        showToast({ title: '已保存，待审核', icon: 'success' })
      } else {
        await api.createMerchantProduct(payload)
        showToast({ title: '已提交审核', icon: 'success' })
      }
      setTimeout(() => navigateBack(), 800)
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const parentNames = new Map<number, string>()
  categories.forEach((item) => {
    if (item.parent === null) parentNames.set(item.id, item.name)
  })
  const parentsWithChildren = new Set(
    categories.filter((item) => item.parent !== null).map((item) => item.parent as number),
  )
  const leafOptions = categories
    .filter((item) => item.parent !== null || !parentsWithChildren.has(item.id))
    .map((item) => ({
      id: item.id,
      label: item.parent !== null ? `${parentNames.get(item.parent) ?? ''} / ${item.name}` : item.name,
    }))
  const ownCategoryOptions = [{ id: 0, label: '不设置本店分类' }].concat(
    merchantCategories.map((item) => ({ id: item.id, label: item.name })),
  )

  const categoryIndex = Math.max(
    leafOptions.findIndex((item) => String(item.id) === form.category_id),
    0,
  )
  const ownCategoryIndex = Math.max(
    ownCategoryOptions.findIndex((item) => String(item.id) === (form.merchant_category_id || '0')),
    0,
  )

  return (
    <View className="page">
      <View className="title">{version !== null ? '编辑商品' : '发布商品'}</View>
      {productStatus === 'PENDING_AUDIT' && <View className="muted">商品审核中，暂不可编辑。</View>}
      {error && (
        <View className="muted" aria-live="polite">
          {error}
        </View>
      )}

      <View className="card">
        <Text className="field-label">商品类型</Text>
        <View style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
          {[
            { value: 'PHYSICAL', label: '实物商品' },
            { value: 'SERVICE', label: '到店服务' },
            { value: 'COUPON', label: '卡券核销' },
          ].map((item) => (
            <Button
              key={item.value}
              className={`chip ${form.type === item.value ? 'active' : ''}`}
              onClick={() => changeType(item.value as 'PHYSICAL' | 'SERVICE' | 'COUPON')}
            >
              {item.label}
            </Button>
          ))}
        </View>

        <Text className="field-label">平台类目</Text>
        <Picker
          mode="selector"
          range={leafOptions}
          rangeKey="label"
          value={categoryIndex}
          onChange={(event) => patch({ category_id: String(leafOptions[Number(event.detail.value)]?.id ?? '') })}
        >
          <View className="input">
            {form.category_id
              ? leafOptions.find((item) => String(item.id) === form.category_id)?.label
              : leafOptions.length
                ? '请选择平台类目…'
                : '平台暂无可选类目'}
          </View>
        </Picker>

        <Text className="field-label">本店分类（选填）</Text>
        <Picker
          mode="selector"
          range={ownCategoryOptions}
          rangeKey="label"
          value={ownCategoryIndex}
          onChange={(event) => {
            const selected = ownCategoryOptions[Number(event.detail.value)]
            patch({ merchant_category_id: selected && selected.id ? String(selected.id) : '' })
          }}
        >
          <View className="input">
            {ownCategoryOptions.find((item) => String(item.id) === (form.merchant_category_id || '0'))?.label}
          </View>
        </Picker>

        <Text className="field-label">商品编码（商户货号，选填）</Text>
        <Input
          className="input"
          name="product_code"
          placeholder="如：AB-001，本店内唯一…"
          value={form.product_code}
          onInput={(event) => patch({ product_code: event.detail.value })}
        />

        <Text className="field-label">标题</Text>
        <Input
          className="input"
          name="title"
          placeholder="请输入商品标题…"
          value={form.title}
          onInput={(event) => patch({ title: event.detail.value })}
        />

        <Text className="field-label">副标题</Text>
        <Input
          className="input"
          name="subtitle"
          placeholder="选填…"
          value={form.subtitle}
          onInput={(event) => patch({ subtitle: event.detail.value })}
        />

        <Text className="field-label">售价（元）</Text>
        <Input
          className="input"
          name="price"
          type="digit"
          placeholder="如：88.00…"
          value={form.price}
          onInput={(event) => patch({ price: event.detail.value })}
        />

        <Text className="field-label">划线价（元，选填）</Text>
        <Input
          className="input"
          name="original_price"
          type="digit"
          placeholder="如：120.00…"
          value={form.original_price}
          onInput={(event) => patch({ original_price: event.detail.value })}
        />

        <Text className="field-label">封面图 URL（选填）</Text>
        <Input
          className="input"
          name="cover_url"
          placeholder="https://…"
          value={form.cover_url}
          onInput={(event) => patch({ cover_url: event.detail.value })}
        />

        <Text className="field-label">详情描述（选填）</Text>
        <Textarea
          className="input"
          name="description"
          placeholder="商品说明、使用规则…"
          value={form.description}
          onInput={(event) => patch({ description: event.detail.value })}
        />
      </View>

      <View className="card">
        <Text className="field-label">履约方式</Text>
        <View style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {DELIVERY_OPTIONS[form.type].map((item) => (
            <Button
              key={item.value}
              className={`chip ${form.delivery_types.includes(item.value) ? 'active' : ''}`}
              onClick={() => toggleDelivery(item.value)}
            >
              {item.label}
            </Button>
          ))}
        </View>

        {form.type === 'PHYSICAL' && (
          <View style={{ marginBottom: '12px' }}>
            <Text className="field-label">商户接单</Text>
            <Button
              className={`chip ${form.acceptance_required ? 'active' : ''}`}
              onClick={() => patch({ acceptance_required: !form.acceptance_required })}
            >
              {form.acceptance_required ? '下单后需接单' : '支付后直接履约'}
            </Button>
          </View>
        )}

        {form.type === 'SERVICE' && (
          <View style={{ marginBottom: '12px' }}>
            <Text className="field-label">核销有效期（天）</Text>
            <Input
              className="input"
              name="verify_days"
              type="number"
              value={form.verify_days}
              onInput={(event) => patch({ verify_days: event.detail.value })}
            />
            {form.delivery_types.includes('APPOINTMENT') && (
              <Button
                className={`chip ${form.appointment_required ? 'active' : ''}`}
                onClick={() => patch({ appointment_required: !form.appointment_required })}
              >
                {form.appointment_required ? '需预约' : '不需预约'}
              </Button>
            )}
          </View>
        )}

        {form.type === 'COUPON' && (
          <View>
            <Text className="field-label">有效期类型</Text>
            <View style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
              {[
                { value: 'DAYS', label: 'N 天有效' },
                { value: 'PERMANENT', label: '永久有效' },
                { value: 'RANGE', label: '固定时间段' },
              ].map((item) => (
                <Button
                  key={item.value}
                  className={`chip ${form.valid_type === item.value ? 'active' : ''}`}
                  onClick={() => patch({ valid_type: item.value as 'DAYS' | 'PERMANENT' | 'RANGE' })}
                >
                  {item.label}
                </Button>
              ))}
            </View>

            {form.valid_type === 'DAYS' && (
              <View style={{ marginBottom: '12px' }}>
                <Text className="field-label">购买后有效天数</Text>
                <Input
                  className="input"
                  name="valid_days"
                  type="number"
                  value={form.valid_days}
                  onInput={(event) => patch({ valid_days: event.detail.value })}
                />
              </View>
            )}

            {form.valid_type === 'RANGE' && (
              <View style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
                <View style={{ flex: 1 }}>
                  <Text className="field-label">生效日期</Text>
                  <Picker
                    mode="date"
                    value={form.valid_from}
                    onChange={(event) => patch({ valid_from: String(event.detail.value) })}
                  >
                    <View className="input">{form.valid_from || '请选择'}</View>
                  </Picker>
                </View>
                <View style={{ flex: 1 }}>
                  <Text className="field-label">失效日期</Text>
                  <Picker
                    mode="date"
                    value={form.valid_to}
                    onChange={(event) => patch({ valid_to: String(event.detail.value) })}
                  >
                    <View className="input">{form.valid_to || '请选择'}</View>
                  </Picker>
                </View>
              </View>
            )}

            <Text className="field-label">可用星期（不选=不限）</Text>
            <View style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '12px' }}>
              {WEEKDAY_OPTIONS.map((item) => (
                <Button
                  key={item.value}
                  className={`chip ${form.usable_weekdays.includes(item.value) ? 'active' : ''}`}
                  onClick={() => toggleWeekday(item.value)}
                >
                  {item.label}
                </Button>
              ))}
            </View>

            <Button
              className={`chip ${form.exclude_holidays ? 'active' : ''}`}
              onClick={() => patch({ exclude_holidays: !form.exclude_holidays })}
            >
              {form.exclude_holidays ? '法定节假日不可用' : '节假日可用'}
            </Button>

            <Text className="field-label">可核销次数</Text>
            <Input
              className="input"
              name="verify_count"
              type="number"
              value={form.verify_count}
              onInput={(event) => patch({ verify_count: event.detail.value })}
            />
            <View className="muted">按次数生成对应数量的独立核销码，全部核销后订单完成。</View>
          </View>
        )}
      </View>

      <View className="card">
        <View className="row">
          <Text className="field-label">SKU 规格</Text>
          <Button className="chip" onClick={addSku}>
            添加 SKU
          </Button>
        </View>
        {skus.map((sku, index) => (
          <View key={index} style={{ borderTop: '1px solid #e4e8ee', paddingTop: '10px', marginTop: '10px' }}>
            <Input
              className="input"
              name={`sku_code_${index}`}
              placeholder="SKU 编码，如 A…"
              value={sku.sku_code}
              onInput={(event) => updateSku(index, { sku_code: event.detail.value })}
            />
            <Input
              className="input"
              name={`sku_spec_${index}`}
              placeholder="规格名，如 标准份…"
              value={sku.spec_name}
              onInput={(event) => updateSku(index, { spec_name: event.detail.value })}
            />
            <Input
              className="input"
              name={`sku_price_${index}`}
              type="digit"
              placeholder="售价（元）…"
              value={sku.price}
              onInput={(event) => updateSku(index, { price: event.detail.value })}
            />
            <Input
              className="input"
              name={`sku_stock_${index}`}
              type="number"
              placeholder="可售数量…"
              value={sku.stock}
              onInput={(event) => updateSku(index, { stock: event.detail.value })}
            />
            <Button className="chip" disabled={skus.length <= 1} onClick={() => removeSku(index)}>
              删除该 SKU
            </Button>
          </View>
        ))}
      </View>

      <Button
        className="btn"
        disabled={saving || productStatus === 'PENDING_AUDIT'}
        onClick={submit}
      >
        {saving ? '保存中…' : version !== null ? '保存并提交审核' : '提交审核'}
      </Button>
    </View>
  )
}
