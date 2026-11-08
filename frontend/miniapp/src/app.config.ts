export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/product/index',
    'pages/cart/index',
    'pages/checkout/index',
    'pages/orders/index',
    'pages/order-detail/index',
    'pages/me/index',
    'pages/login/index',
    'pages/merchant/index',
    'pages/merchant/orders/index',
    'pages/merchant/verify/index',
    'pages/merchant/statements/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: '异业联盟',
    navigationBarTextStyle: 'black',
  },
  tabBar: {
    color: '#52606d',
    selectedColor: '#2f6bff',
    backgroundColor: '#ffffff',
    list: [
      { pagePath: 'pages/index/index', text: '首页' },
      { pagePath: 'pages/cart/index', text: '购物车' },
      { pagePath: 'pages/orders/index', text: '订单' },
      { pagePath: 'pages/me/index', text: '我的' },
    ],
  },
})
