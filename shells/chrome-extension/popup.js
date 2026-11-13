// Chrome 外掛骨架（Manifest V3）：讀目前分頁的 Codeforces 題號 → 查資料包 → 60 秒反思 → AI 整理成洞見卡。
// API key 不放在外掛裡：所有 LLM 呼叫都經過本機後端（server/app.py）。
const SERVER = "http://127.0.0.1:8787";   // 改埠號時，manifest.json 的 host_permissions 也要一起改
const $ = (s) => document.querySelector(s);
let problem = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(SERVER + path, opt);
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// https://codeforces.com/contest/1005/problem/D、/problemset/problem/1005/D → CF1005D
function cfIdFromUrl(url) {
  const m = /codeforces\.com\/(?:contest\/(\d+)\/problem|problemset\/problem\/(\d+))\/([A-Za-z]\d?)/.exec(url || "");
  return m ? `CF${m[1] || m[2]}${m[3].toUpperCase()}` : null;
}

function showProblem(p, note) {
  problem = p;
  $("#problem-name").textContent = p ? `${p.id} · ${p.title}（${p.difficulty}）` : "—";
  $("#problem-note").textContent = note || (p ? p.tags.join("、") : "");
}

async function init() {
  try {
    const h = await api("/api/health");
    $("#status").textContent = h.dry_run ? "後端已連線 · dry-run（回傳範例）" : `後端已連線 · ${h.provider} ${h.model}`;
  } catch {
    $("#status").textContent = "連不到後端：請先執行 python server/app.py";
    $("#status").classList.add("err");
    $("#submit").disabled = true;
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const id = cfIdFromUrl(tab?.url);
  const list = await api("/api/problems");
  if (id && list.some((p) => p.id === id)) {
    showProblem(await api(`/api/problems/${id}`));
  } else {
    // 不在 Codeforces 題目頁、或這題不在資料包：讓使用者從資料包搜尋一題（正式版可以改成自己存題目資訊）
    $("#picker").hidden = false;
    $("#problem-options").innerHTML = list.map((p) => `<option value="${esc(p.id)}">${esc(p.title)}（${p.difficulty}）</option>`).join("");
    const note = id ? `目前分頁是 ${id}，不在資料包裡；先從資料包選一題示範。` : "目前分頁不是 Codeforces 題目頁；先從資料包選一題。";
    const search = $("#problem-search");
    search.onchange = async () => {
      const pid = search.value.trim().toUpperCase().split(/\s/)[0];
      if (list.some((p) => p.id === pid)) showProblem(await api(`/api/problems/${pid}`), note);
    };
    search.value = list[0].id;
    await search.onchange();
  }
  renderCards();
}

$("#form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!problem) return;
  const btn = $("#submit");
  btn.disabled = true;
  const t0 = Date.now();
  $("#result").innerHTML = `<div class="card">AI 整理中… <span id="sec">0</span> 秒</div>`;
  const timer = setInterval(() => { const s = $("#sec"); if (s) s.textContent = Math.round((Date.now() - t0) / 1000); }, 500);
  try {
    const r = await api("/api/demo/reflect", {
      problem: problem.id,
      stuck: document.querySelector('input[name="stuck"]:checked')?.value || "",
      observation: $("#observation").value.trim(),
      simulate: $("#simulate").value,
    });
    const log = `<ol class="log">${r.log.map((l) => `<li>${esc(l)}</li>`).join("")}</ol>`;
    if (!r.ok) {
      $("#result").innerHTML = `<div class="card error"><b>這次沒整理成功</b>，你的回答還在，可以再按一次。<div>${esc(r.error)}</div>${log}</div>`;
      return;
    }
    const card = { ...r.data, problem: problem.id, title: problem.title, at: new Date().toISOString() };
    const { cards = [] } = await chrome.storage.local.get("cards");
    await chrome.storage.local.set({ cards: [card, ...cards] });
    $("#result").innerHTML = `<div class="card"><div class="trigger">看到：${esc(card.trigger)}</div>
      <div><span class="arrow">→</span> 想到：${esc(card.action)}</div>
      <div class="note">追問：${esc(card.follow_up)}</div>${log}</div>`;
    $("#observation").value = "";
    renderCards();
  } catch (err) {
    $("#result").innerHTML = `<div class="card error"><b>連線失敗</b><div>${esc(err.message)}</div></div>`;
  } finally {
    clearInterval(timer);
    btn.disabled = false;
  }
});

async function renderCards() {
  const { cards = [] } = await chrome.storage.local.get("cards");
  $("#card-count").textContent = cards.length ? `（${cards.length} 張）` : "";
  $("#cards").innerHTML = cards.slice(0, 3).map((c) =>
    `<li>${esc(c.trigger)} <span class="arrow">→</span> ${esc(c.action)}<div class="from">${esc(c.problem)} · ${esc(c.at.slice(0, 10))}</div></li>`).join("")
    || `<li class="from">還沒有洞見卡。</li>`;
}

init();
