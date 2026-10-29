/* 登录页接线自检：node tools/check_login.js */
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');

const html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');
const js = fs.readFileSync(path.join(ROOT, 'web', 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(ROOT, 'web', 'style.css'), 'utf8');

const ids = new Set([...html.matchAll(/id="([\w-]+)"/g)].map((m) => m[1]));
const used = [...new Set([...js.matchAll(/\$\('#([\w-]+)'\)/g)].map((m) => m[1]))];
const missing = used.filter((x) => !ids.has(x));

const checks = {
  '错误框元素存在': ids.has('loginErr'),
  '错误框有显示态样式': /\.err\.show/.test(css),
  '错误框默认隐藏': /\.err\s*\{[^}]*display:\s*none/.test(css),
  '401 不再被登录接口吞掉': js.includes('raw401'),
  '空账号/空密码有提示': js.includes('请输入账号') && js.includes('请输入密码'),
  '登录中按钮态': js.includes("'登录中…'"),
  '失败清空密码并抖动': js.includes('shake'),
  '打开页面清空旧错误': js.includes('setLoginError(\'\')'),
  '没有任何账号密码提示残留': !/demo2026|judge2026|data-u="demo"/.test(html + js),
};

let ok = missing.length === 0;
for (const [k, v] of Object.entries(checks)) {
  if (!v) ok = false;
  console.log((v ? '✓' : '✗') + ' ' + k);
}
console.log('\n缺失 DOM id:', missing.length ? missing.join(', ') : '无');
console.log('结果：', ok ? '通过' : '未通过');
process.exit(ok ? 0 : 1);
