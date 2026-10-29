/* 自测：命中率 / 拒答率 / 时延。node tools/selftest.js */
const fs = require('fs');
const path = require('path');
const E = require(path.join(__dirname, '..', 'web', 'engine.js'));

const KB = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'kb.json'), 'utf8'));
const idx = E.createIndex(KB);

const PARAPHRASE = [
  ['宝塔山的塔是明朝的吗', 'A02'],
  ['七大在哪开的', 'A04'],
  ['文艺座谈会是哪年', 'A05'],
  ['南泥湾是谁开垦的', 'A18'],
  ['从西安坐高铁到延安要多久', 'C01'],
  ['延安机场通哪些城市', 'C02'],
  ['纪念馆要门票吗', 'S01'],
  ['纪念馆怎么预约', 'S02'],
  ['壶口瀑布门票多少钱', 'S23'],
  ['黄帝陵在哪里', 'A21'],
  ['中共中央在延安几年', 'B01'],
  ['枣园是什么地方', 'A06'],
  ['清凉山上的新华社', 'A16'],
  ['梁家河收门票吗', 'E04'],
  ['今天场馆开门吗', 'E01'],
  ['能帮我订票吗', 'E03'],
];

const OOS = [
  '北京今天天气怎么样', '帮我写一段 Python 代码', '延安房价多少', '推荐一部电影',
  '苹果手机怎么截屏', '洛川苹果多少钱一斤', '西安到成都高铁', '介绍一下你自己',
  '1+1 等于几', '延安大学怎么样', '帮我订机票', '昨天有什么新闻', '如何学习英语',
  '延安精神是什么', '红色旅游的定义', '给我讲个笑话',
];

let selfHit = 0, selfFail = [];
for (const e of KB.entries) {
  const r = E.ask(idx, e.q, 'fact');
  const ok = !r.refused && r.entryId === e.id;
  if (ok) selfHit++; else selfFail.push({ q: e.q, got: r.entryId || (r.refused ? 'REFUSED' : '?'), score: +r.score.toFixed(3) });
}

let paraHit = 0, paraFail = [];
for (const [q, want] of PARAPHRASE) {
  const r = E.ask(idx, q, 'fact');
  const got = r.refused ? 'REFUSED' : r.entryId;
  if (got === want) paraHit++; else paraFail.push({ q, want, got, score: +r.score.toFixed(3) });
}

let oosOk = 0, oosFail = [], oosSoft = 0;
for (const q of OOS) {
  const r = E.ask(idx, q, 'fact');
  if (r.refused) { oosOk++; continue; }
  // 命中「拒答样板」不算错：它回答的仍是"我不能确认"
  const e = KB.entries.find(x => x.id === r.entryId);
  if (e && e.kind === '拒答样板') { oosSoft++; continue; }
  oosFail.push({ q, got: r.entryId, score: +r.score.toFixed(3), text: r.text.slice(0, 30) });
}

// 时延
const t0 = process.hrtime.bigint();
for (let i = 0; i < 200; i++) E.ask(idx, KB.entries[i % KB.entries.length].q, 'fact');
const ms = Number(process.hrtime.bigint() - t0) / 1e6 / 200;

const report = {
  kb: { count: KB.entries.length, sources: KB.sources, version: KB.version },
  self: { total: KB.entries.length, hit: selfHit, rate: +(selfHit / KB.entries.length * 100).toFixed(1), fail: selfFail },
  paraphrase: { total: PARAPHRASE.length, hit: paraHit, rate: +(paraHit / PARAPHRASE.length * 100).toFixed(1), fail: paraFail },
  outOfScope: { total: OOS.length, refused: oosOk, soft: oosSoft, fail: oosFail.length, failList: oosFail },
  latencyMs: +ms.toFixed(2),
  threshold: E.THRESHOLD,
};
fs.writeFileSync(path.join(__dirname, '..', 'docs', 'selftest.json'), JSON.stringify(report, null, 1));
console.log(JSON.stringify(report, null, 1));
