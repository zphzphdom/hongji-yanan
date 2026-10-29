/* 红迹·延安 —— 检索与作答引擎（无外部依赖，浏览器与 Node 共用）
 * 设计原则：只答知识库；分数不够就拒答；每条答案必须能挂上来源。 */
(function (root) {
  'use strict';

  var PUNCT = /[\s\u3000，。！？、；：""''（）()《》〈〉·…—\-_,.!?;:'"\[\]{}<>\/\\|@#$%^&*+=~`]+/g;
  var CJK = /[\u4e00-\u9fa5]/;

  function norm(s) {
    return String(s || '').toLowerCase().replace(PUNCT, '');
  }

  function grams(s) {
    var t = norm(s), out = new Set(), i, seg, m;
    var parts = t.match(/[a-z0-9]+|[\u4e00-\u9fa5]+/g) || [];
    for (i = 0; i < parts.length; i++) {
      seg = parts[i];
      if (CJK.test(seg)) {
        if (seg.length === 1) { out.add(seg); continue; }
        for (m = 0; m < seg.length - 1; m++) out.add(seg.substr(m, 2));
      } else {
        out.add(seg);
      }
    }
    return out;
  }

  function createIndex(kb) {
    var entries = kb.entries.slice();
    var df = Object.create(null);
    var i, g;
    for (i = 0; i < entries.length; i++) {
      var e = entries[i];
      var doc = (e.q || '') + '。' + (e.a || '') + '。' + (e.tags || []).join(' ');
      e._qG = grams(e.q);
      e._g = grams(doc);
      e._qNorm = norm(e.q);
      e._seen = Object.create(null);
      e._g.forEach(function (k) {
        if (!e._seen[k]) { e._seen[k] = 1; df[k] = (df[k] || 0) + 1; }
      });
    }
    var N = entries.length;
    var idf = Object.create(null);
    Object.keys(df).forEach(function (k) { idf[k] = Math.log((N + 1) / (df[k] + 1)) + 1; });
    var maxIdf = Math.log(N + 1) + 1;

    // 实体表（场馆/旧址/人名）与意图表（预约/门票/开门…）分开：
    // 实体决定"讲哪个点"，意图只用来放宽阈值，避免"洛川苹果多少钱"被"多少钱"带去答门票。
    var tagMap = Object.create(null);
    var intentMap = Object.create(null);
    entries.forEach(function (e, j) {
      (e.tags || []).forEach(function (t) {
        var k = norm(t);
        if (!k) return;
        (tagMap[k] || (tagMap[k] = [])).push(j);
      });
      (e.itags || []).forEach(function (t) {
        var k = norm(t);
        if (!k) return;
        (intentMap[k] || (intentMap[k] = [])).push(j);
      });
    });
    var byLen = function (a, b) { return b.length - a.length; };
    return {
      kb: kb, entries: entries, idf: idf, maxIdf: maxIdf, N: N,
      tagMap: tagMap, intentMap: intentMap,
      tagList: Object.keys(tagMap).sort(byLen),
      intentList: Object.keys(intentMap).sort(byLen)
    };
  }

  function scoreEntry(idx, e, qG, qNorm) {
    var total = 0, hit = 0, qhit = 0, g, w;
    qG.forEach(function (k) {
      w = idx.idf[k] || idx.maxIdf;
      total += w;
      if (e._seen[k]) { hit += w; if (e._qG.has(k)) qhit += w; }
    });
    if (total <= 0) return { score: 0, coverage: 0 };
    var coverage = hit / total;
    var questionSide = qhit / total;
    var score = coverage * 0.55 + questionSide * 0.45;
    // 整句包含：问法与知识库问题几乎一致
    if (qNorm && e._qNorm) {
      if (e._qNorm.indexOf(qNorm) >= 0 || qNorm.indexOf(e._qNorm) >= 0) score = Math.max(score, 0.96);
    }
    return { score: score, coverage: coverage };
  }

  function rank(idx, candidates, qG, qNorm) {
    var scored = [];
    for (var i = 0; i < candidates.length; i++) {
      var e = candidates[i];
      var r = scoreEntry(idx, e, qG, qNorm);
      if (r.score > 0.02) scored.push({ entry: e, score: r.score, coverage: r.coverage });
    }
    scored.sort(function (a, b) { return b.score - a.score; });
    return scored;
  }

  function groupRank(idx, map, key, qG, qNorm) {
    var cands = [], want = Object.create(null);
    map[key].forEach(function (j) { if (!want[j]) { want[j] = 1; cands.push(idx.entries[j]); } });
    return rank(idx, cands, qG, qNorm);
  }

  function search(idx, query, topk) {
    var qG = grams(query), qNorm = norm(query);
    var i, local;

    // 1) 先看命中哪个实体（句子最长优先）
    var ent = [];
    for (i = 0; i < idx.tagList.length; i++) {
      if (qNorm.indexOf(idx.tagList[i]) >= 0) ent.push(idx.tagList[i]);
    }
    if (ent.length) {
      // 多个实体同时出现时（"延安苹果和洛川苹果的区别"），看它覆盖了问句的多少；
      // 覆盖不足一半的实体（如大词"延安"）只是背景词，不参与路由。
      var bestList = null, bestRatio = 0, bestTag = '', bestScore = 0;
      for (i = 0; i < ent.length; i++) {
        var ratio = ent[i].length / qNorm.length;
        local = groupRank(idx, idx.tagMap, ent[i], qG, qNorm);
        if (!local.length) continue;
        var better = ratio > bestRatio + 1e-6 ||
          (Math.abs(ratio - bestRatio) <= 1e-6 && local[0].score > bestScore);
        if (better) {
          bestRatio = ratio;
          bestScore = local[0].score;
          bestList = local;
          bestTag = ent[i];
        }
      }
      if (bestList && bestRatio >= 0.5 && bestScore >= 0.20) {
        bestList.forEach(function (s) { s.viaTag = true; s.tags = [bestTag]; });
        return bestList.slice(0, topk || 5);
      }
      // 实体只是背景词、或库里说不清 —— 回全库按阈值判，不降级去猜意图
      return rank(idx, idx.entries, qG, qNorm).slice(0, topk || 5);
    }

    // 2) 没有实体，再看意图词（预约/门票/开门/天气…），只用来放宽阈值
    for (i = 0; i < idx.intentList.length; i++) {
      if (qNorm.indexOf(idx.intentList[i]) < 0) continue;
      local = groupRank(idx, idx.intentMap, idx.intentList[i], qG, qNorm);
      if (local.length && local[0].score >= 0.22) {
        local.forEach(function (s) { s.viaTag = true; s.tags = [idx.intentList[i]]; });
        return local.slice(0, topk || 5);
      }
    }
    return rank(idx, idx.entries, qG, qNorm).slice(0, topk || 5);
  }

  var REFUSE = '这个问题我需要查证，建议咨询延安市文旅局或对应场馆的官方渠道。为避免提供不准确的信息，我不做推测。';
  var OFF_ROUTE = '我只熟悉延安的红色文旅，这条线路我没有可引用的资料，不做推测。建议查 12306 或地图应用规划行程。';
  var OFF_TOPIC = '我只负责延安红色文旅的讲解，这个问题帮不上忙。想听听“延安十三年”里发生了什么吗？';
  var THRESHOLD = 0.33;

  // 结构护栏：只服务「来延安」的行程与史实问题
  function guard(query, idx) {
    var m = query.match(/(?:从)?(.{1,10}?)到(.{1,10}?)(?:怎么|如何|要|需要|多久|多远|坐|乘|开车|高铁|飞机|火车|自驾)/);
    if (m) {
      var dest = m[2];
      var known = idx.tagList.some(function (t) { return dest.indexOf(t) >= 0; });
      if (dest.indexOf('延安') < 0 && !known) return OFF_ROUTE;
    }
    if (/(今天|昨天|明天|本周|最近|现在).{0,6}(新闻|热点|热搜|头条)/.test(query)) return REFUSE;
    if (/(写|生成|编)[^，。]{0,4}(代码|程序|脚本)/.test(query) || /python|java\b/i.test(query)) return OFF_TOPIC;
    if (/大学|学院|中学|小学/.test(query) && /怎么样|好不好|排名|分数线|学费|就业/.test(query)) return OFF_TOPIC;
    return null;
  }

  function splitSentences(text) {
    return String(text || '').split(/(?<=[。！？；])/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function firstClause(text, max) {
    var s = String(text || '').replace(/\s+/g, '');
    var m = s.match(/^[^。！？；]*[。！？；]?/);
    var out = (m ? m[0] : s) || s;
    max = max || 60;
    return out.length > max ? out.slice(0, max - 1) + '…' : out;
  }

  function composeResearch(entry) {
    if (entry.kind === '拒答样板') return entry.a;
    var sents = splitSentences(entry.a);
    var what = sents[0] || entry.a;
    var why = sents[1] || '';
    var think = '想一想：如果让你向同伴介绍这里，你会先讲哪一件事？为什么？';
    if (/门票|预约|开放|时间/.test(entry.q)) think = '想一想：为什么纪念馆要把“免费”做成一项制度？';
    else if (/多少|几个|哪年|什么时候|年代/.test(entry.q)) think = '想一想：这些数字是怎么统计出来的？换个口径会变成多少？';
    else if (/为什么|原因|意义/.test(entry.q)) think = '想一想：如果换成你来讲，你会用哪一件展品说明这一点？';
    else think = '想一想：把刚听到的这一段，用一句话讲给没来过延安的人听。';
    var out = '看什么：' + what;
    if (why) out += '\n为什么重要：' + why;
    out += '\n' + think;
    return out;
  }

  function composeMoment(entry) {
    if (entry.kind === '拒答样板') return entry.a;
    var line = firstClause(entry.a, 58);
    return line + ' #延安红色之旅';
  }

  function compose(entry, mode) {
    if (mode === 'research') return composeResearch(entry);
    if (mode === 'moment') return composeMoment(entry);
    return entry.a;
  }

  function ask(idx, query, mode) {
    query = String(query || '').trim();
    if (!query) return { refused: true, text: '问点什么吧，比如“宝塔山为什么是延安的象征？”。', sources: [], score: 0 };
    var g = guard(query, idx);
    if (g) return { refused: true, text: g, sources: [], score: 0, guarded: true };
    var hits = search(idx, query, 5);
    var best = hits[0];
    var ok = best && (best.score >= THRESHOLD || (best.viaTag && best.score >= 0.20));
    if (!ok) {
      return { refused: true, text: REFUSE, sources: [], score: best ? best.score : 0, hits: hits };
    }
    var entry = best.entry;
    return {
      refused: false,
      entryId: entry.id,
      question: entry.q,
      text: compose(entry, mode || 'fact'),
      raw: entry.a,
      mode: mode || 'fact',
      sources: entry.sources || [],
      image: entry.image || null,
      kind: entry.kind,
      scene: entry.scene,
      conf: entry.conf,
      score: best.score,
      alt: hits.slice(1, 3).map(function (h) { return { id: h.entry.id, q: h.entry.q, score: h.score }; })
    };
  }

  var api = {
    norm: norm, grams: grams, createIndex: createIndex, search: search,
    ask: ask, compose: compose, REFUSE: REFUSE, THRESHOLD: THRESHOLD
  };
  root.RedEngine = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
