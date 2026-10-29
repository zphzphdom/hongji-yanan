const E = require('../../utils/engine.js');
const KB = require('../../data/kb.js');
const app = getApp();

const CHIPS = ['A01', 'A09', 'A04', 'A18', 'S01', 'B05', 'C01', 'E04'];
const MODE_NOTE = {
  fact: '史实问答',
  research: '研学讲解词',
  moment: '一句话',
};

Page({
  data: {
    meta: '',
    mode: 'fact',
    messages: [],
    input: '',
    chips: [],
    anchor: '',
    sending: false,
  },

  onLoad() {
    this.idx = E.createIndex(KB);
    const chips = CHIPS.map((id) => {
      const e = KB.entries.filter((x) => x.id === id)[0];
      return e ? e.q.replace(/？$/, '') : '';
    }).filter(Boolean);
    this.setData({
      chips,
      count: KB.count,
      meta: `知识库 v${KB.version} · ${KB.count} 条 · ${KB.sources} 个来源`,
    });
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  setMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({ mode });
    wx.showToast({ title: MODE_NOTE[mode], icon: 'none' });
  },

  useChip(e) {
    const q = e.currentTarget.dataset.q;
    this.ask(q);
  },

  send() {
    this.ask(this.data.input);
  },

  ask(text) {
    text = String(text || '').trim();
    if (!text || this.data.sending) return;
    const mode = this.data.mode;
    const msgs = this.data.messages.concat([{ role: 'me', text }]);
    const aiIndex = msgs.length;
    msgs.push({ role: 'ai', text: '正在查知识库…', loading: true, sources: [] });
    this.setData({ messages: msgs, input: '', sending: true, anchor: 'm' + aiIndex });

    setTimeout(() => {
      let r;
      try {
        r = E.ask(this.idx, text, mode);
      } catch (err) {
        r = { refused: true, text: '引擎出了点问题，请退出重进。', sources: [] };
      }
      this.render(text, r, aiIndex);
    }, 260);
  },

  render(question, r, aiIndex) {
    const item = {
      role: 'ai',
      text: r.text,
      refused: !!r.refused,
      loading: false,
      sources: (r.sources || []).map((s) => ({ id: s.id, org: s.org, doc: s.doc, date: s.date, url: s.url })),
      note: r.refused ? '' : MODE_NOTE[this.data.mode],
      question,
      entryId: r.entryId || '',
      raw: r.raw || r.text,
    };
    const patch = {};
    patch['messages[' + aiIndex + ']'] = item;
    patch.sending = false;
    patch.anchor = 'm' + aiIndex;
    this.setData(patch);

    if (app.globalData.useLLM && app.globalData.apiBase && !r.refused && r.raw) {
      this.llmRewrite(item, aiIndex, question, r);
    }
  },

  // 可选：自建服务改写语气（域名需备案并加入 request 合法域名）
  llmRewrite(item, aiIndex, question, r) {
    wx.request({
      url: app.globalData.apiBase + '/api/chat',
      method: 'POST',
      timeout: 20000,
      data: { question, answer: r.raw, mode: this.data.mode, id: r.entryId },
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.ok && res.data.answer) {
          const patch = {};
          patch['messages[' + aiIndex + '].text'] = res.data.answer;
          patch['messages[' + aiIndex + '].note'] = MODE_NOTE[this.data.mode] + ' · 模型改写';
          this.setData(patch);
        }
      },
    });
  },

  onSource(e) {
    const s = e.currentTarget.dataset.src;
    wx.showModal({
      title: '来源 ' + s.id,
      content: `${s.org}\n《${s.doc}》\n${s.date}\n\n链接已复制，可粘贴到浏览器查看原文。`,
      confirmText: '复制链接',
      cancelText: '知道了',
      success: (res) => {
        if (res.confirm && s.url) {
          wx.setClipboardData({ data: s.url });
        }
      },
    });
  },

  makeCard(e) {
    const i = e.currentTarget.dataset.i;
    const item = this.data.messages[i];
    if (!item) return;
    app.globalData.cardPayload = {
      question: item.question,
      text: item.text,
      sources: item.sources,
      ip: '红迹·延安',
      agent: '延小讲',
    };
    wx.navigateTo({ url: '/pages/card/card' });
  },

  copyText(e) {
    const i = e.currentTarget.dataset.i;
    const item = this.data.messages[i];
    const s = (item.sources || [])[0];
    const summary = String(item.text || '').replace(/\s+/g, '').slice(0, 52);
    const txt = `我问了「${item.question}」，它告诉我：${summary}——来自延安 AI 讲解员「延小讲」。` +
      (s ? `（来源：${s.id} ${s.org}《${s.doc}》${s.date}）` : '');
    wx.setClipboardData({ data: txt });
  },

  onShareAppMessage() {
    return {
      title: '在延安，问一句有出处的话',
      path: '/pages/index/index',
    };
  },
});
