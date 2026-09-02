// VoiceTherapy 定制咨询师客户端 —— 接 runner /api/offer（同域反代）
import { PipecatClient, RTVIEvent } from "https://esm.sh/@pipecat-ai/client-js@1.12.0";
import { SmallWebRTCTransport } from "https://esm.sh/@pipecat-ai/small-webrtc-transport@1.10.5";

const BOT_URL = "/api/offer";
const $ = (id) => document.getElementById(id);
const connectBtn = $("connectBtn");
const exitBtn = $("exitBtn");
const badge = $("connBadge");
const statusEl = $("status");
const hintEl = $("hintText");
const heroTitle = $("heroTitle");
const avatar = $("avatar");
const chat = $("chat");
const timerWrap = $("timerWrap");
const timerEl = $("timer");

let client;
let botAudio = null;
let micTrack = null;          // 本地麦克风轨道(用于暂停)
let listening = true;         // 是否在听
let botBubble = null;         // 当前咨询师气泡
let userBubble = null;        // 当前用户气泡
let timerInt = null, startTs = 0;

function fmt(sec) { return `${String(Math.floor(sec/60)).padStart(2,"0")}:${String(sec%60).padStart(2,"0")}`; }
function startTimer() { startTs = Date.now(); timerEl.textContent = "00:00"; timerWrap.hidden = false; clearInterval(timerInt); timerInt = setInterval(()=>{ timerEl.textContent = fmt(Math.floor((Date.now()-startTs)/1000)); }, 1000); }
function stopTimer() { clearInterval(timerInt); timerInt = null; }
function durText() { const s = Math.floor((Date.now()-startTs)/1000); return `${Math.floor(s/60)}分${s%60}秒`; }

const states = { OFF:0, CONNECTING:1, ON:2 }; // 是否已建连(不含暂停)
let connState = states.OFF;

function setState() {
  connectBtn.classList.remove("connecting","talking","listening","paused");
  avatar.classList.remove("listening","talking");
  if (connState === states.OFF) {
    badge.textContent = "未连接"; badge.className = "badge offline";
    hintEl.textContent = "开始"; heroTitle.textContent = "想聊聊吗？";
    connectBtn.setAttribute("aria-label","开始对话");
    exitBtn.hidden = true; timerWrap.hidden = true;
  } else {
    exitBtn.hidden = false;
    if (listening) {
      badge.textContent = "正在聆听"; badge.className = "badge online";
      connectBtn.classList.add("listening"); avatar.classList.add("listening");
      hintEl.textContent = "点按暂停"; heroTitle.textContent = "我在听，请说";
    } else {
      badge.textContent = "已暂停"; badge.className = "badge talking";
      connectBtn.classList.add("paused"); avatar.classList.remove("listening");
      hintEl.textContent = "点按继续"; heroTitle.textContent = "已暂停，点按继续";
    }
  }
}

function botTalking(on) {
  if (on) { connectBtn.classList.add("talking"); avatar.classList.add("talking"); statusEl.textContent = "咨询师在说…"; }
  else { connectBtn.classList.remove("talking"); avatar.classList.remove("talking"); statusEl.textContent = listening ? "我在听" : "已暂停"; }
}

function addBubble(who) {
  const b = document.createElement("div");
  b.className = "bubble " + who;
  chat.appendChild(b); chat.scrollTop = chat.scrollHeight;
  return b;
}

// #3/#4：用户实时转写（final 才定稿）
function onUserTranscript(data) {
  if (!data) return;
  if (!userBubble || userBubble.dataset.final === "1") { userBubble = addBubble("user"); userBubble.dataset.final = "0"; }
  userBubble.textContent = data.text || "…";
  if (data.final) { userBubble.dataset.final = "1"; statusEl.textContent = "听到，我想想…"; }
  chat.scrollTop = chat.scrollHeight;
}

// #4：咨询师文字(流式拼接进同一气泡)
function onBotTtsText(data) {
  if (!data?.text) return;
  if (!botBubble) { botBubble = addBubble("bot"); }
  botBubble.textContent += data.text;
  chat.scrollTop = chat.scrollHeight;
  botTalking(true);
}

function startTurnGap() { botBubble = null; botTalking(false); }

function ensureBotAudio() {
  if (botAudio) return botAudio;
  botAudio = document.createElement("audio");
  botAudio.autoplay = true;
  document.body.appendChild(botAudio);
  return botAudio;
}

async function connect() {
  connectBtn.disabled = true;
  connState = states.CONNECTING; badge.textContent = "连接中…"; badge.className="badge offline";
  try {
    client = new PipecatClient({ transport: new SmallWebRTCTransport(), enableMic: true, enableCam: false });

    client.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (track.kind !== "audio") return;
      if (participant?.local) { micTrack = track; return; }
      ensureBotAudio().srcObject = new MediaStream([track]);
      startTurnGap();
    });
    client.on(RTVIEvent.TrackStopped, (track) => {
      if (track?.kind === "audio" && !track?.local) startTurnGap();
    });
    client.on(RTVIEvent.UserStartedSpeaking, () => { userBubble = null; });
    client.on(RTVIEvent.UserTranscript, (d) => onUserTranscript(d));
    client.on(RTVIEvent.BotTtsText, (d) => onBotTtsText(d));
    client.on(RTVIEvent.BotConnected, () => { connState = states.ON; listening = true; startTimer(); setState(); });
    client.on(RTVIEvent.Disconnected, () => endSession());

    await client.connect({ webrtcUrl: BOT_URL });
    addBubble("bot").textContent = "你好，我在。想聊聊什么？";
    connState = states.ON; listening = true; startTimer();
    connectBtn.disabled = false;      // #1 修复：连接成功要重新可用，否则点不了
    setState();
  } catch (err) {
    console.error("Connect failed:", err);
    connState = states.OFF;
    addBubble("bot").textContent = "连接失败：" + (err?.message ?? err);
    connectBtn.disabled = false;
    setState();
  }
}

// #2 暂停/继续：mute/unmute 本地麦克风
function togglePause() {
  if (connState !== states.ON) return;
  listening = !listening;
  if (micTrack) micTrack.enabled = listening;
  if (!listening) { botTalking(false); }
  setState();
}

function collectTranscript() {
  const out = [];
  for (const el of chat.children) {
    if (!el.classList || !el.classList.contains("bubble")) continue;
    const text = (el.textContent || "").trim();
    if (!text) continue;
    const who = el.classList.contains("user") ? "user" : "bot";
    out.push({ who, text });
  }
  return out;
}

async function saveSession() {  // #5：把对话写进知识库
  const turns = collectTranscript();
  if (turns.length === 0) { heroTitle.textContent = "这次没说什么，没保存"; return null; }
  try {
    const r = await fetch("/api/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration_s: Math.floor((Date.now()-startTs)/1000), transcript: turns }),
    });
    const j = await r.json();
    if (j.ok) return j;            // {filename, path}
    return null;
  } catch (e) { console.error("save failed", e); return null; }
}

async function endSession() {  // 退出 → 计时停止 → 保存到知识库
  exitBtn.disabled = true;
  stopTimer();
  try { await client?.disconnect(); } finally {
    if (botAudio) botAudio.srcObject = null;
    client = undefined; botBubble = null; userBubble = null;
    connState = states.OFF; listening = true; micTrack = null;
    // 显示结束 + 保存结果
    heroTitle.textContent = "今天聊到这儿。";
    const saved = await saveSession();
    if (saved) {
      addBubble("bot").textContent = `✅ 已保存到知识库：${saved.path}（时长 ${durText()}）`;
    } else {
      addBubble("bot").textContent = `已结束（时长 ${durText()}）。需要的话随时回来。`;
    }
    connectBtn.disabled = false; exitBtn.disabled = false; exitBtn.hidden = true;
    setState();
  }
}

connectBtn.addEventListener("click", () => {
  if (connState === states.ON) togglePause();
  else if (connState === states.OFF) connect();
});
exitBtn.addEventListener("click", endSession);
