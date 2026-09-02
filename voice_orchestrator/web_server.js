#!/usr/bin/env node
/*
VoiceTherapy 定制咨询师界面 —— 静态 + 反向代理服务器（零依赖，Node http）。
- 服务 voice_orchestrator/web_client/ 下的自定义页面（root → index.html）
- 其余路径(/api/offer、/start、/client 等)反代到 runner 127.0.0.1:7860，同域免跨域

用途：tailscale serve 根路径 → 本服务器端口(默认 8050)，手机开 https://mac….ts.net/ 即见定制界面。
起法: node web_server.js [port]   （默认 8050）
*/
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.argv[2] || 8050);
const RUNNER = "127.0.0.1";
const RUNNER_PORT = 7860;
const WEB_ROOT = path.join(__dirname, "web_client");
// vault 会谈目录(写 AI 访谈记录)
const VAULT_SESSION_DIR = process.env.VT_VAULT
  ? path.join(process.env.VT_VAULT, "咨询/来访者/我/会谈")
  : path.join(process.env.HOME || "",
      "Library/Mobile Documents/iCloud~md~obsidian/Documents/Vaults/Jeff",
      "咨询/来访者/我/会谈");
const VOICE_MODE = "voice";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};

function serveStatic(req, res, urlPath) {
  let rel = urlPath === "/" ? "/index.html" : urlPath;
  const file = path.join(WEB_ROOT, rel);
  // 防目录穿越
  if (!file.startsWith(WEB_ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
    res.end(data);
  });
}

function readBody(req) {
  return new Promise((resolve) => {
    let d = "";
    req.on("data", (c) => (d += c));
    req.on("end", () => { try { resolve(JSON.parse(d)); } catch { resolve({}); } });
  });
}

function pad(n) { return String(n).padStart(2, "0"); }
function nowLocal() {
  const d = new Date();
  return { date: `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`,
           hm: `${pad(d.getHours())}:${pad(d.getMinutes())}` };
}

async function saveAiSession(body) {
  // body: { transcript:[{who:'user'|'bot', text}], duration_s }
  const { date, hm } = nowLocal();
  const filename = `${date}-AI-访谈.md`;
  const file = path.join(VAULT_SESSION_DIR, filename);
  fs.mkdirSync(VAULT_SESSION_DIR, { recursive: true });

  const turns = Array.isArray(body?.transcript) ? body.transcript : [];
  const durMin = Math.max(0, Math.round((body?.duration_s || 0) / 60));
  const dur = `${Math.floor((body?.duration_s||0)/60)}分${(body?.duration_s||0)%60}秒`;

  const lines = [
    "---",
    `date: ${date}`,
    "type: AI",
    `mode: ${VOICE_MODE}`,
    `source: 手机语音 · AI访谈`,
    `duration: ${dur}`,
    "---",
    `# ${date} AI访谈（语音）`,
    "",
    `> ${date} ${hm} · 时长 ${dur} · 经语音对话完成`,
    "",
    "## 逐字记录",
    "",
  ];
  for (const t of turns) {
    if (!t?.text) continue;
    const who = t.who === "user" ? "我" : "咨询师";
    lines.push(`> **${who}**：${t.text.trim()}`);
    lines.push("");
  }
  if (turns.length === 0) lines.push("> （本次无有效文字记录）", "");
  lines.push(`--- 记录自动保存于 ${date} ${hm}，共 ${durMin} 分钟、${turns.length} 条语句 ---`);
  fs.writeFileSync(file, lines.join("\n"), "utf8");
  return { filename, path: `会谈/${filename}` };
}

function proxy(req, res) {
  const p = new URL(req.url, "http://x");
  const opts = {
    hostname: RUNNER, port: RUNNER_PORT, method: req.method,
    path: p.pathname + p.search, headers: { ...req.headers, host: `${RUNNER}:${RUNNER_PORT}` },
  };
  const preq = http.request(opts, (pres) => {
    res.writeHead(pres.statusCode, pres.headers);
    pres.pipe(res);
  });
  preq.on("error", () => { res.writeHead(502); res.end("runner down"); });
  req.pipe(preq);
}

const server = http.createServer(async (req, res) => {
  const urlPath = new URL(req.url, "http://x").pathname;
  if (req.method === "POST" && urlPath === "/api/save") {
    const body = await readBody(req);
    try {
      const r = await saveAiSession(body);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, ...r }));
    } catch (e) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: String(e && e.message || e) }));
    }
    return;
  }
  if (urlPath.startsWith("/api/") || urlPath.startsWith("/start") ||
      urlPath.startsWith("/client") || urlPath.startsWith("/docs") ||
      urlPath.startsWith("/rtvi")) {
    return proxy(req, res);           // 信令 & runner 自带 UI 转发给 7860
  }
  return serveStatic(req, res, urlPath); // 自定义页面静态
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[vt-web] 自定义咨询师界面  http://127.0.0.1:${PORT}  (静态 web_client + 反代 runner ${RUNNER_PORT})`);
});
