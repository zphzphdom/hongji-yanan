/* 前端接线自检：app.js 里引用的每个 DOM id 必须存在于 index.html。node tools/check_dom.js */
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');

const html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');
const js = fs.readFileSync(path.join(ROOT, 'web', 'app.js'), 'utf8');

const ids = new Set([...html.matchAll(/id="([\w-]+)"/g)].map(m => m[1]));
const used = [...new Set([...js.matchAll(/\$\('#([\w-]+)'\)/g)].map(m => m[1]))];
const missing = used.filter(x => !ids.has(x));

const kb = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'kb.json'), 'utf8'));
const chipIds = [...js.matchAll(/CHIPS\s*=\s*\[([^\]]+)\]/g)].map(m => m[1]).join(',');
const chips = (chipIds.match(/'([A-Z]\d+)'/g) || []).map(s => s.replace(/'/g, ''));
const badChips = chips.filter(c => !kb.entries.some(e => e.id === c));

const out = {
  domIds: ids.size,
  selectors: used.length,
  missingInHtml: missing,
  chips: chips.length,
  chipsNotInKb: badChips,
  kb: { count: kb.entries.length, sources: kb.sources, version: kb.version },
  ok: missing.length === 0 && badChips.length === 0
};
console.log(JSON.stringify(out, null, 1));
process.exit(out.ok ? 0 : 1);
