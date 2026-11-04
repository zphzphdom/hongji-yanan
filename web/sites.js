/* 点位一览子页：每个点位独立成页 */
(function () {
  'use strict';
  var A = window.APP;
  A.post('/api/progress', {}).then(function (j) {
    var sites = (j.sites || []).filter(function (s) {
      return !s.region || s.region === A.region;
    });
    var box = document.getElementById('siteList');
    if (!sites.length) {
      box.innerHTML = '<div class="empty">该地区暂无点位</div>';
      return;
    }
    box.innerHTML = sites.map(function (s) {
      return '<a class="sitecard" href="site.html?r=' + encodeURIComponent(A.region) +
        '&site=' + encodeURIComponent(s.id) + '">' +
        '<span class="sc-no">' + (s.no || '') + '</span>' +
        '<span class="sc-main"><b>' + A.esc(s.name) + '</b>' +
        '<em>' + A.esc(s.level || '') + (s.done ? ' · 已完成' : '') + '</em></span>' +
        '<span class="sc-arrow">→</span></a>';
    }).join('');
  }).catch(function () {
    document.getElementById('siteList').innerHTML = '<div class="empty">加载失败</div>';
  });
})();
