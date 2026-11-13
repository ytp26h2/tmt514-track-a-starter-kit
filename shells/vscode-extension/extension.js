// VS Code 擴充套件骨架：純 JavaScript，不需要 npm install、不需要編譯。
// 在 VS Code 開啟 shells/vscode-extension 資料夾，按 F5 就會開一個載入這個擴充套件的新視窗。
// 想改成 TypeScript：npx --package yo --package generator-code -- yo code，再把這裡的邏輯搬過去。
const vscode = require("vscode");

const VERDICT = { OK: "AC", AC: "AC", WA: "WA", TLE: "TLE", RE: "RE", CE: "CE", "?": "?" };
let output;
let statusItem;

function serverUrl() {
  return vscode.workspace.getConfiguration("ytp").get("serverUrl", "http://127.0.0.1:8787").replace(/\/$/, "");
}

async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  let res;
  try {
    res = await fetch(serverUrl() + path, opt);
  } catch (e) {
    throw new Error(`連不到後端 ${serverUrl()}：請先在 starter kit 根目錄執行 python server/app.py`);
  }
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function languageOf(doc) {
  if (doc.languageId === "cpp" || doc.languageId === "c") return "cpp";
  if (doc.languageId === "python") return "python";
  return null;
}

// 每個檔案記住對應哪一題（存在 workspaceState，重開 VS Code 也還在）
function problemKey(doc) { return `ytp.problem:${doc.uri.toString()}`; }

function currentProblem(context, doc) {
  // 檔名像 CF1005D.cpp、1005D.py 就自動對應
  const m = /(?:CF)?(\d{3,4}[A-Z]\d?)/i.exec(doc.fileName.split(/[\\/]/).pop() || "");
  return context.workspaceState.get(problemKey(doc)) || (m ? `CF${m[1].toUpperCase()}` : undefined);
}

function updateStatus(context) {
  const ed = vscode.window.activeTextEditor;
  const pid = ed ? currentProblem(context, ed.document) : undefined;
  statusItem.text = pid ? `$(beaker) ${pid}` : "$(beaker) YTP：選題";
  statusItem.tooltip = "YTP：選擇這個檔案對應的資料包題目";
  statusItem.show();
}

async function pickProblem(context) {
  const ed = vscode.window.activeTextEditor;
  if (!ed) return vscode.window.showWarningMessage("先開啟一個程式檔。");
  const list = await api("/api/problems");
  const pick = await vscode.window.showQuickPick(
    list.map((p) => ({ label: `${p.id} · ${p.title}`, description: `${p.difficulty}`, detail: p.tags.join("、"), id: p.id })),
    { placeHolder: "這個檔案是在寫哪一題？" });
  if (!pick) return undefined;
  await context.workspaceState.update(problemKey(ed.document), pick.id);
  updateStatus(context);
  return pick.id;
}

async function reviewCode(context) {
  const ed = vscode.window.activeTextEditor;
  if (!ed) return vscode.window.showWarningMessage("先開啟一個程式檔。");
  const code = ed.selection.isEmpty ? ed.document.getText() : ed.document.getText(ed.selection);
  if (!code.trim()) return vscode.window.showWarningMessage("檔案是空的。");
  const pid = currentProblem(context, ed.document);
  const r = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AI 正在看你的程式碼…", cancellable: false },
    () => api("/api/demo/review", { code, language: languageOf(ed.document) || ed.document.languageId, problem: pid }));
  output.clear();
  output.appendLine(`=== AI 分析${pid ? `（${pid}）` : ""}${r.dry_run ? "  [dry-run 範例]" : ""} ===`);
  if (!r.ok) {
    output.appendLine(`沒拿到可用的分析：${r.error}`);
  } else {
    output.appendLine(`想做什麼：${r.data.intent}`);
    output.appendLine(`時間複雜度：${r.data.complexity}`);
    output.appendLine("可能出錯的地方：");
    r.data.risks.forEach((x) => output.appendLine(`  - ${x}`));
  }
  output.appendLine("");
  output.appendLine(`程式檢查紀錄（${r.attempts} 次、${r.seconds} 秒）：`);
  r.log.forEach((x) => output.appendLine(`  ${x}`));
  output.show(true);
  return r;
}

async function runExamples(context) {
  const ed = vscode.window.activeTextEditor;
  if (!ed) return vscode.window.showWarningMessage("先開啟一個程式檔。");
  const language = languageOf(ed.document);
  if (!language) return vscode.window.showWarningMessage("目前支援 C++ 和 Python。");
  const pid = currentProblem(context, ed.document) || await pickProblem(context);
  if (!pid) return undefined;
  const r = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `用 ${pid} 的範例測資跑…` },
    () => api("/api/judge/examples", { problem: pid, language, code: ed.document.getText() }));
  output.clear();
  if (r.status === "CE") {
    output.appendLine("編譯錯誤：");
    output.appendLine(r.stderr);
  } else {
    const ac = r.verdicts.filter((v) => v.status === "AC").length;
    output.appendLine(`=== ${pid} 範例測資：${ac}/${r.verdicts.length} 通過 ===`);
    for (const v of r.verdicts) {
      output.appendLine(`[${VERDICT[v.status] || v.status}] ${v.name}  ${(v.seconds * 1000).toFixed(0)} ms`);
      if (v.status !== "AC") {
        output.appendLine(`  預期：${v.expected.trim()}`);
        output.appendLine(`  輸出：${v.got.trim()}`);
        if (v.stderr) output.appendLine(`  stderr：${v.stderr.trim().slice(0, 500)}`);
      }
    }
    if (r.checker === "special") output.appendLine("（這題答案不唯一，? 需要自己確認）");
  }
  output.show(true);
  return r;
}

function wrap(fn, context) {
  return async () => {
    try { return await fn(context); } catch (e) { vscode.window.showErrorMessage(`YTP：${e.message}`); }
  };
}

function activate(context) {
  output = vscode.window.createOutputChannel("YTP");
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusItem.command = "ytp.pickProblem";
  context.subscriptions.push(
    output, statusItem,
    vscode.commands.registerCommand("ytp.pickProblem", wrap(pickProblem, context)),
    vscode.commands.registerCommand("ytp.reviewCode", wrap(reviewCode, context)),
    vscode.commands.registerCommand("ytp.runExamples", wrap(runExamples, context)),
    vscode.window.onDidChangeActiveTextEditor(() => updateStatus(context)),
  );
  updateStatus(context);
}

function deactivate() {}

module.exports = { activate, deactivate };
