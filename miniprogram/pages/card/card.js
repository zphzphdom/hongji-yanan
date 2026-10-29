const app = getApp();

Page({
  data: {
    ready: false,
    saving: false,
    hasCode: false,
  },

  onLoad() {
    this.payload = app.globalData.cardPayload || null;
    if (!this.payload) {
      wx.showToast({ title: '没有可生成的内容', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 800);
    }
  },

  onReady() {
    if (!this.payload) return;
    this.draw();
  },

  draw() {
    wx.createSelectorQuery()
      .select('#card')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0]) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const W = 1080;
        const H = 1440;
        canvas.width = W;
        canvas.height = H;
        this.canvas = canvas;

        this.render(ctx, W, H);
        this.setData({ ready: true });

        // 若能拿到小程序码图片（/images/wxacode.png），画进卡里
        try {
          const img = canvas.createImage();
          img.onload = () => {
            this.codeImg = img;
            this.render(ctx, W, H);
            this.setData({ hasCode: true });
          };
          img.src = '/images/wxacode.png';
        } catch (e) {}
      });
  },

  wrap(ctx, text, x, y, maxW, lh, maxLines) {
    let line = '';
    let lines = 0;
    const s = String(text || '').replace(/\s+/g, ' ');
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      const test = line + ch;
      if (ctx.measureText(test).width > maxW && line) {
        ctx.fillText(line, x, y);
        y += lh;
        line = ch;
        lines += 1;
        if (lines >= maxLines) {
          ctx.fillText(line.slice(0, -1) + '…', x, y);
          return y;
        }
      } else {
        line = test;
      }
    }
    if (line) {
      ctx.fillText(line, x, y);
      y += lh;
    }
    return y;
  },

  render(ctx, W, H) {
    const p = this.payload;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#FAF5EF';
    ctx.fillRect(0, 0, W, H);

    const grad = ctx.createLinearGradient(0, 0, W, 360);
    grad.addColorStop(0, '#8C1F28');
    grad.addColorStop(1, '#6B1219');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, 300);
    ctx.fillStyle = '#B0863A';
    ctx.fillRect(0, 300, W, 4);

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '700 74px serif';
    ctx.fillText('红迹·延安', 80, 140);
    ctx.fillStyle = 'rgba(250,245,239,.86)';
    ctx.font = '400 30px sans-serif';
    ctx.fillText('AI 讲解员 · 延小讲｜在延安，问一句有出处的话', 80, 196);
    ctx.fillStyle = 'rgba(176,134,58,.95)';
    ctx.font = '400 24px sans-serif';
    ctx.fillText('延安 · 1935—1948', 80, 250);

    let y = 388;
    ctx.fillStyle = '#B0863A';
    ctx.font = '600 24px sans-serif';
    ctx.fillText('我问了', 80, y);
    y += 62;

    ctx.fillStyle = '#211A17';
    ctx.font = '700 44px serif';
    y = this.wrap(ctx, '「' + p.question + '」', 80, y, 920, 62, 2) + 32;

    ctx.fillStyle = '#B0863A';
    ctx.font = '600 24px sans-serif';
    ctx.fillText('它说', 80, y);
    y += 58;

    ctx.fillStyle = '#3A2E29';
    ctx.font = '400 34px sans-serif';
    y = this.wrap(ctx, p.text, 80, y, 920, 54, 5) + 26;

    const s = (p.sources || [])[0];
    if (s) {
      ctx.fillStyle = 'rgba(176,134,58,.10)';
      ctx.fillRect(64, y - 34, W - 128, 96);
      ctx.fillStyle = '#8C1F28';
      ctx.font = '600 22px sans-serif';
      ctx.fillText('来源 ' + s.id + ' · ' + s.org, 88, y + 4);
      ctx.fillStyle = '#6E625C';
      ctx.font = '400 20px sans-serif';
      const doc = s.doc.length > 30 ? s.doc.slice(0, 29) + '…' : s.doc;
      ctx.fillText(doc + '　' + s.date, 88, y + 38);
      y += 96;
    }

    // 小程序码区（有图就用图，没图留占位）
    const qs = 250;
    const qx = W - 80 - qs;
    const qy = H - 80 - qs;
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(qx - 14, qy - 14, qs + 28, qs + 28);
    ctx.strokeStyle = '#E7DCD3';
    ctx.lineWidth = 2;
    ctx.strokeRect(qx - 14, qy - 14, qs + 28, qs + 28);
    if (this.codeImg) {
      ctx.drawImage(this.codeImg, qx, qy, qs, qs);
    } else {
      ctx.strokeStyle = '#D9C9C9';
      ctx.strokeRect(qx, qy, qs, qs);
      ctx.fillStyle = '#A6978E';
      ctx.font = '400 26px sans-serif';
      ctx.fillText('小程序码', qx + 62, qy + 118);
      ctx.font = '400 20px sans-serif';
      ctx.fillText('红迹·延安', qx + 72, qy + 158);
    }
    ctx.fillStyle = '#6E625C';
    ctx.font = '400 22px sans-serif';
    ctx.fillText('扫码继续问', qx + 58, qy + qs + 46);

    ctx.fillStyle = '#211A17';
    ctx.font = '400 26px sans-serif';
    ctx.fillText('我问到了什么，也留下了出处。', 80, H - 120);
    ctx.fillStyle = '#A6978E';
    ctx.font = '400 20px sans-serif';
    ctx.fillText('红迹·延安 · 只答有来源的史实', 80, H - 78);

    ctx.fillStyle = 'rgba(140,31,40,.9)';
    ctx.beginPath();
    ctx.arc(W - 120, 120, 66, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#F3D9B8';
    ctx.textAlign = 'center';
    ctx.font = '700 30px serif';
    ctx.fillText('延安', W - 120, 118);
    ctx.font = '400 18px sans-serif';
    ctx.fillText('1935—1948', W - 120, 146);
    ctx.textAlign = 'left';
  },

  save() {
    if (!this.canvas || this.data.saving) return;
    this.setData({ saving: true });
    wx.canvasToTempFilePath({
      canvas: this.canvas,
      x: 0,
      y: 0,
      width: 1080,
      height: 1440,
      destWidth: 1080,
      destHeight: 1440,
      success: (r) => {
        wx.saveImageToPhotosAlbum({
          filePath: r.tempFilePath,
          success: () => {
            this.setData({ saving: false });
            wx.showToast({ title: '已保存到相册' });
          },
          fail: (err) => {
            this.setData({ saving: false });
            if (String(err.errMsg).indexOf('auth') >= 0) {
              wx.showModal({
                title: '需要相册权限',
                content: '保存问答卡需要写入相册，去设置里打开即可。',
                confirmText: '去设置',
                success: (m) => { if (m.confirm) wx.openSetting(); },
              });
            } else {
              wx.showToast({ title: '保存失败，请重试', icon: 'none' });
            }
          },
        });
      },
      fail: () => {
        this.setData({ saving: false });
        wx.showToast({ title: '生成图片失败', icon: 'none' });
      },
    });
  },

  onShareAppMessage() {
    return {
      title: '我在延安问到了什么',
      path: '/pages/index/index',
      imageUrl: '',
    };
  },
});
