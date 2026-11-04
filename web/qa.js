/* 史实问答子页：简洁版 */
(function () {
  'use strict';
  var A = window.APP, mode = 'fact', busy = false;
  var $ = A.$;

  [].forEach.call(document.querySelectorAll('#qaModes .mode'), function (b) {
    b.onclick = function () {
      mode = b.dataset.mode;
      [].forEach.call(document.querySelectorAll('#qaModes .mode'), function (x) {
        x.classList.toggle('on', x === b);
      });
    };
  });

  function ask() {
    var q = ($('#qaInput').value || '').trim();
    if (!q || busy) return;
    busy = true;
    var box = $('#qaAnswer');
    box.innerHTML = '<div class="qa-loading"><i></i><i></i><i></i></div>';
    A.post('/api/ask', { question: q, mode: mode }).then(function (r) {
      busy = false;
      if (!r || !r.ok) {
        box.innerHTML = '<div class="qa-err">暂时无法联网生成，请稍后重试。</div>';
        return;
      }
      render(q, r);
      loadImage(r, q);
    }).catch(function () {
      busy = false;
      box.innerHTML = '<div class="qa-err">网络异常，请重试。</div>';
    });
  }

  function render(q, r) {
    var box = $('#qaAnswer');
    var html = '<div class="qa-q">' + A.esc(q) + '</div>' +
      '<div class="qa-a">' + A.esc(r.text || '').replace(/\n/g, '<br>') + '</div>';
    var v = r.verdict || {};
    if (v.reason) html += '<div class="qa-verdict">' + A.esc(v.reason) + '</div>';
    var kb = r.kb || [];
    if (kb.length) {
      html += '<div class="qa-hits"><span class="qa-hits-t">命中条目</span>' + kb.map(function (k) {
        return '<span class="qa-hit">' + A.esc(k.id) + ' · ' + (k.chars || 0) + ' 字</span>';
      }).join('') + '</div>';
    }
    var web = r.web || [];
    if (web.length) {
      html += '<div class="qa-src">' + web.map(function (w) {
        return '<a href="' + A.esc(w.url) + '" target="_blank" rel="noopener">' +
          A.esc(w.site || '来源') + (w.date ? ' · ' + A.esc(w.date) : '') + '</a>';
      }).join('') + '</div>';
    }
    html += '<div class="qa-img" id="qaImg"><span class="qa-img-tip">正在联网找相关图片…</span></div>';
    box.innerHTML = html;
  }

  function loadImage(r, q) {
    var host = $('#qaImg');
    if (!host) return;
    A.post('/api/img', { keys: r.imageKeys || [], context: ((r.text || '') + ' ' + q).slice(0, 300) })
      .then(function (j) {
        if (!j || !j.url) { host.innerHTML = '<span class="qa-img-tip">未找到足够相关的图片</span>'; return; }
        host.innerHTML = '<img src="' + A.esc(j.url) + '" alt="' + A.esc(j.alt || '') +
          '" referrerpolicy="no-referrer" loading="lazy">' +
          '<div class="qa-img-c">' + A.esc(j.credit || '') + '</div>';
      }).catch(function () { host.innerHTML = ''; });
  }

  $('#qaSend').onclick = ask;
  $('#qaInput').onkeydown = function (e) { if (e.key === 'Enter') ask(); };
})();
