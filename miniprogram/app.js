App({
  globalData: {
    cardPayload: null,
    // 联网改写开关：默认关。小程序调用外部接口要求域名已备案并加入「request 合法域名」，
    // 备案域名就绪后把 useLLM 改 true，并把 apiBase 换成自己的域名。
    useLLM: false,
    apiBase: '',
  },
  onLaunch() {},
});
