/* 大图浮层自检：node tools/check_lightbox.js */
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');
const js = fs.readFileSync(path.join(ROOT, 'web', 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'web', 'style.css'), 'utf8');

const checks = {
  '有关闭按钮': js.includes("'lb-close'") && js.includes('✕ 关闭'),
  '点空白或图片可关': js.includes('closeLightbox();') && js.includes("e.target.tagName === 'IMG'"),
  'ESC 可关': js.includes("e.key === 'Escape'"),
  '关闭时清空并解绑事件': js.includes('box.onclick = null') && js.includes("removeEventListener('keydown', escClose)"),
  '按钮有样式': css.includes('.lb-close'),
  '浮层层级够高': /\.lightbox\s*\{[^}]*z-index:\s*120/.test(css),
  '图片加载失败有提示': js.includes('图片加载失败'),
  '打开时重置旧内容': js.includes("box.innerHTML = ''"),
};

let ok = true;
for (const [k, v] of Object.entries(checks)) {
  if (!v) ok = false;
  console.log((v ? '✓ ' : '✗ ') + k);
}
console.log('\n结果：', ok ? '通过' : '未通过');
process.exit(ok ? 0 : 1);
