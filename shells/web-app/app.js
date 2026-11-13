// Web 應用程式骨架：純 HTML + JS，不需要 build。後端（server/app.py）同時提供這個頁面和 API。
// 想改用 React / Vue / Vite 都可以；記得把開發伺服器的網址加進 .env 的 ALLOWED_ORIGINS。
const API = window.API_BASE || "";            // 同一個來源時留空即可
const $ = (sel) => document.querySelector(sel);
const state = { problem: null, list: [] };
const SHORT = { OK: "AC", WRONG_ANSWER: "WA", TIME_LIMIT_EXCEEDED: "TLE", RUNTIME_ERROR: "RE",
  MEMORY_LIMIT_EXCEEDED: "MLE", COMPILATION_ERROR: "CE" };

// ---- 小工具 ---------------------------------------------------------------
async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const res = await fetch(API + path, opt);
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// 很陽春的 Markdown：標題、清單、段落、行內 code、程式碼區塊。數學式 $…$ 保留原樣。
function md(text) {
  const out = [];
  String(text).split(/```/).forEach((chunk, i) => {
    if (i % 2 === 1) { out.push(`<pre class="code">${esc(chunk.replace(/^\w*\n/, ""))}</pre>`); return; }
    let list = [];
    const flush = () => { if (list.length) { out.push(`<ul>${list.join("")}</ul>`); list = []; } };
    for (const para of chunk.split(/\n{2,}/)) {
      for (const line of para.split("\n")) {
        const t = esc(line).replace(/`([^`]+)`/g, "<code>$1</code>");
        if (/^#{1,6} /.test(line)) { flush(); out.push(`<h3>${t.replace(/^#+ /, "")}</h3>`); }
        else if (/^\s*[-•] /.test(line)) list.push(`<li>${t.replace(/^\s*[-•] /, "")}</li>`);
        else if (line.trim()) { flush(); out.push(`<p>${t}</p>`); }
      }
      flush();
    }
  });
  return out.join("");
}

// ---- 狀態列 ---------------------------------------------------------------
async function loadHealth() {
  const el = $("#status");
  try {
    const h = await api("/api/health");
    const d = h.datapack;
    el.textContent = h.dry_run
      ? `dry-run（沒有 API key，回傳範例）· 資料包 ${d.problems} 題`
      : `${h.provider} ${h.model} · 資料包 ${d.problems} 題`;
    el.className = "status " + (h.dry_run ? "dry" : "live");
  } catch (e) {
    el.textContent = "連不到後端：請先執行 python server/app.py";
    el.className = "status err";
  }
}

// ---- 題目列表與內容 ---------------------------------------------------------
async function loadProblems() {
  state.list = await api("/api/problems");
  renderList();
  $("#search").addEventListener("input", renderList);
  $("#band").addEventListener("change", renderList);
  $("#problem-list").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) openProblem(b.dataset.id);
  });
}

// 題目一多（例如 cf1000-v0.1），就需要搜尋：題號、題名、標籤都能搜，另外可以篩難度
function renderList() {
  const q = $("#search").value.trim().toLowerCase();
  const [lo, hi] = ($("#band").value || "0-9999").split("-").map(Number);
  const shown = state.list.filter((p) => p.difficulty >= lo && p.difficulty <= hi &&
    (!q || p.id.toLowerCase().includes(q) || p.title.toLowerCase().includes(q) || p.tags.some((t) => t.includes(q))));
  const LIMIT = 300;  // 一次最多畫 300 筆，避免列表太長
  $("#list-count").textContent = `顯示 ${Math.min(shown.length, LIMIT)} / 符合 ${shown.length} / 共 ${state.list.length} 題`;
  $("#problem-list").innerHTML = shown.slice(0, LIMIT).map((p) =>
    `<li><button data-id="${esc(p.id)}" class="${state.problem?.id === p.id ? "active" : ""}"><span>${esc(p.id)} · ${esc(p.title)}</span><span class="rating">${p.difficulty}</span></button></li>`).join("");
}

async function openProblem(id) {
  const p = await api(`/api/problems/${encodeURIComponent(id)}`);
  state.problem = p;
  document.querySelectorAll("#problem-list button").forEach((b) => b.classList.toggle("active", b.dataset.id === id));
  $("#empty").hidden = true;
  $("#problem").hidden = false;
  $("#p-id").textContent = `${p.id} · ${p.source?.contest ?? ""}`;
  $("#p-title").textContent = p.title;
  $("#p-meta").innerHTML = `<span class="chip rating">${p.difficulty}</span>` + p.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("");
  const ex = p.examples.map((e, i) => `<div><div class="label">範例 ${i + 1} 輸入</div><pre class="code">${esc(e.input)}</pre></div>
    <div><div class="label">範例 ${i + 1} 輸出</div><pre class="code">${esc(e.output)}</pre></div>`).join("");
  $("#p-statement").innerHTML = md(p.statement) + `<h3>範例</h3><div class="examples">${ex}</div>`;
  $("#hint-btn").disabled = false;
  $("#ai-out").innerHTML = "";
  $("#judge-result").innerHTML = "";
  await loadSubmissions(p.id);
}

async function loadSubmissions(pid) {
  const subs = await api(`/api/submissions?problem=${encodeURIComponent(pid)}`);
  $("#sub-count").textContent = subs.length ? `(${subs.length})` : "";
  $("#sub-code").hidden = true;
  $("#sub-list").innerHTML = subs.length ? subs.map((s) =>
    `<li><button data-sid="${esc(s.id)}"><span class="verdict v-${esc(s.verdict)}">${esc(SHORT[s.verdict] || s.verdict)}</span>
      <span>${esc(s.language)}</span><span class="muted">${esc(s.user)} · 通過 ${s.passed_tests ?? "?"} 筆</span><span class="muted">${esc(s.id)}</span></button></li>`).join("")
    : `<li class="muted">這題沒有提交紀錄。</li>`;
  $("#sub-list").onclick = async (e) => {
    const b = e.target.closest("button[data-sid]");
    if (!b) return;
    document.querySelectorAll("#sub-list button").forEach((x) => x.classList.toggle("active", x === b));
    const s = await api(`/api/submissions/${encodeURIComponent(b.dataset.sid)}`);
    $("#sub-code").textContent = s.code;
    $("#sub-code").hidden = false;
  };
}

// ---- 分頁 -----------------------------------------------------------------
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  ["statement", "submissions", "judge"].forEach((name) => { $(`#tab-${name}`).hidden = name !== t.dataset.tab; });
}));

// ---- AI 提示：規範三的完整流程 ---------------------------------------------
async function askHint() {
  if (!state.problem) return;
  const out = $("#ai-out");
  const btn = $("#hint-btn");
  btn.disabled = true;
  const t0 = performance.now();
  out.innerHTML = `<div class="card"><span class="spinner"></span>等待 AI 回覆… <span id="elapsed">0.0</span> 秒</div>`;
  const timer = setInterval(() => { const el = $("#elapsed"); if (el) el.textContent = ((performance.now() - t0) / 1000).toFixed(1); }, 100);
  try {
    const r = await api("/api/demo/hint", {
      problem: state.problem.id, level: Number($("#hint-level").value), simulate: $("#simulate").value,
    });
    const log = `<ol class="log">${r.log.map((l) => `<li>${esc(l)}</li>`).join("")}</ol>`;
    if (r.ok) {
      out.innerHTML = `<div class="card hint"><div class="k">第 ${r.data.level} 層提示</div><div>${esc(r.data.hint)}</div></div>
        <div class="card"><div class="k">先回答自己這個問題</div><div>${esc(r.data.key_question)}</div></div>
        <div class="muted small">程式檢查紀錄（${r.attempts} 次、${r.seconds} 秒${r.dry_run ? "、dry-run" : ""}）</div>${log}`;
    } else {
      out.innerHTML = `<div class="card error"><b>這次沒拿到可用的提示。</b><div class="small">${esc(r.error)}</div>
        <button class="btn" id="retry" style="margin-top:8px">再試一次</button></div>${log}`;
      $("#retry").onclick = askHint;
    }
  } catch (e) {
    out.innerHTML = `<div class="card error"><b>連線失敗</b><div class="small">${esc(e.message)}</div></div>`;
  } finally {
    clearInterval(timer);
    btn.disabled = false;
  }
}
$("#hint-btn").addEventListener("click", askHint);

// ---- 用範例測資跑程式 -------------------------------------------------------
$("#judge-btn").addEventListener("click", async () => {
  if (!state.problem) return;
  const box = $("#judge-result");
  box.innerHTML = `<div class="muted"><span class="spinner"></span>編譯、執行中…</div>`;
  try {
    const r = await api("/api/judge/examples", {
      problem: state.problem.id, language: $("#judge-lang").value, code: $("#judge-code").value,
    });
    if (r.status === "CE") { box.innerHTML = `<div class="judge-row"><span class="verdict v-CE">CE</span>編譯錯誤</div><pre class="code">${esc(r.stderr)}</pre>`; return; }
    const note = r.checker === "special" ? `<div class="muted small">這題答案不唯一（special checker），「?」需要自己確認。</div>` : "";
    box.innerHTML = note + r.verdicts.map((v) => `<div class="judge-row"><span class="verdict v-${esc(v.status)}">${esc(v.status)}</span>${esc(v.name)}　${(v.seconds * 1000).toFixed(0)} ms</div>
      ${v.status === "AC" ? "" : `<pre class="code">預期：\n${esc(v.expected)}\n\n你的輸出：\n${esc(v.got)}${v.stderr ? "\n\nstderr：\n" + esc(v.stderr) : ""}</pre>`}`).join("");
  } catch (e) {
    box.innerHTML = `<div class="card error">${esc(e.message)}</div>`;
  }
});

// ---- 隨機抽一題（評審抽測就是這樣抽） ----------------------------------------
$("#random-btn").addEventListener("click", async () => {
  const p = await api("/api/random?kind=problem");
  openProblem(p.id);
});

loadHealth();
loadProblems().catch(() => {});
