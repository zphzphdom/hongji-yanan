/* 自带矢量地图（不依赖任何外部瓦片，离线可用）
   用于瓦片加载失败时兜底：绘制点位、连线、距离、名称，点击弹信息与导航。
   window.MiniMap(el, points, opts)
     points: [{lat,lng,name,desc,addr,nav,search,legKm}]
     opts: {height, accent}
*/
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  window.MiniMap = function (el, points, opts) {
    if (!el) return null;
    opts = opts || {};
    points = (points || []).filter(function (p) {
      return p && typeof p.lat === 'number' && typeof p.lng === 'number';
    });
    if (!points.length) {
      el.innerHTML = '<div class="mm-empty">暂无坐标，可点下方按钮用高德查看</div>';
      return null;
    }

    var W = 720, H = opts.height || 360, PAD = 46;
    var lats = points.map(function (p) { return p.lat; });
    var lngs = points.map(function (p) { return p.lng; });
    var minLat = Math.min.apply(null, lats), maxLat = Math.max.apply(null, lats);
    var minLng = Math.min.apply(null, lngs), maxLng = Math.max.apply(null, lngs);
    var dLat = Math.max(1e-4, maxLat - minLat), dLng = Math.max(1e-4, maxLng - minLng);
    // 保持比例，避免变形
    var scale = Math.min((W - PAD * 2) / dLng, (H - PAD * 2) / dLat);
    var offX = (W - dLng * scale) / 2, offY = (H - dLat * scale) / 2;

    function xy(p) {
      return {
        x: offX + (p.lng - minLng) * scale,
        y: H - offY - (p.lat - minLat) * scale   // 纬度向上
      };
    }

    var accent = opts.accent || '#8C1F28';
    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" class="mm-svg" preserveAspectRatio="xMidYMid meet">',
      '<defs><pattern id="mmGrid" width="36" height="36" patternUnits="userSpaceOnUse">',
      '<path d="M36 0H0V36" fill="none" stroke="#E7DCCF" stroke-width="1"/></pattern></defs>',
      '<rect width="' + W + '" height="' + H + '" fill="#FBF7F1"/>',
      '<rect width="' + W + '" height="' + H + '" fill="url(#mmGrid)"/>'];

    // 连线
    if (points.length > 1) {
      var d = points.map(function (p, i) {
        var q = xy(p);
        return (i ? 'L' : 'M') + q.x.toFixed(1) + ' ' + q.y.toFixed(1);
      }).join(' ');
      svg.push('<path d="' + d + '" fill="none" stroke="' + accent +
        '" stroke-width="2.5" stroke-dasharray="7 6" opacity="0.75"/>');
    }

    // 点与标注
    points.forEach(function (p, i) {
      var q = xy(p);
      svg.push('<g class="mm-node" data-i="' + i + '" tabindex="0" role="button">');
      svg.push('<circle cx="' + q.x.toFixed(1) + '" cy="' + q.y.toFixed(1) +
        '" r="15" fill="' + accent + '" stroke="#fff" stroke-width="2.5"/>');
      svg.push('<text x="' + q.x.toFixed(1) + '" y="' + (q.y + 4.5).toFixed(1) +
        '" text-anchor="middle" font-size="12" fill="#fff" font-weight="700">' + (i + 1) + '</text>');
      svg.push('<text x="' + q.x.toFixed(1) + '" y="' + (q.y - 22).toFixed(1) +
        '" text-anchor="middle" font-size="12" fill="#3A2E29">' + esc(p.name || '') + '</text>');
      if (p.legKm) {
        svg.push('<text x="' + q.x.toFixed(1) + '" y="' + (q.y + 32).toFixed(1) +
          '" text-anchor="middle" font-size="10" fill="#A6978E">↓' + esc(String(p.legKm)) + 'km</text>');
      }
      svg.push('</g>');
    });

    svg.push('</svg>');
    svg.push('<div class="mm-panel" id="mmPanel"><span class="mm-hint">点上方标点查看详情与导航</span></div>');

    el.innerHTML = svg.join('');
    el.classList.add('mm-wrap');

    var panel = el.querySelector('.mm-panel');
    function show(i) {
      var p = points[i];
      panel.innerHTML =
        '<div class="mm-title">' + esc(p.name || '') + '</div>' +
        (p.desc ? '<div class="mm-desc">' + esc(p.desc) + '</div>' : '') +
        (p.addr ? '<div class="mm-addr">' + esc(p.addr) + '</div>' : '') +
        (p.legKm ? '<div class="mm-addr">距下一点约 ' + esc(String(p.legKm)) + ' 公里</div>' : '') +
        '<div class="mm-acts">' +
        (p.nav ? '<a class="mp-btn primary" target="_blank" rel="noopener" href="' + esc(p.nav) + '">开始导航</a>' : '') +
        (p.search ? '<a class="mp-btn" target="_blank" rel="noopener" href="' + esc(p.search) + '">按名称搜</a>' : '') +
        '</div>';
      [].forEach.call(el.querySelectorAll('.mm-node'), function (g) {
        g.classList.toggle('on', Number(g.dataset.i) === i);
      });
    }

    [].forEach.call(el.querySelectorAll('.mm-node'), function (g) {
      g.addEventListener('click', function () { show(Number(g.dataset.i)); });
      g.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { show(Number(g.dataset.i)); }
      });
    });
    show(0);

    return { show: show, isMini: true };
  };
})();
