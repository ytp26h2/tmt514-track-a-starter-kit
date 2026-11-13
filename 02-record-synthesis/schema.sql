-- 解題反思資料庫的資料表。核心設計：「洞見卡 (insight card)」才是複習單位，而不是題目。
CREATE TABLE IF NOT EXISTS problems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT UNIQUE,
    title       TEXT,
    source      TEXT,             -- codeforces / atcoder / tioj / zerojudge / 自訂
    status      TEXT,             -- AC / upsolve (看題解後才過) / gave-up
    minutes     INTEGER,          -- 花了多久
    rating      INTEGER,
    code        TEXT,
    solved_at   TEXT DEFAULT (datetime('now', 'localtime')),
    debriefed   INTEGER DEFAULT 0 -- 是否已做過反思
);
CREATE TABLE IF NOT EXISTS reflections (
    problem_id       INTEGER REFERENCES problems(id),
    key_observation  TEXT,  -- 一句話：解開這題的關鍵觀察
    stuck_point      TEXT,  -- 我卡在哪裡
    unlock_hint      TEXT,  -- 什麼提示會讓我更早解開
    bottleneck       TEXT,  -- thinking / implementation / reading / none
    bugs             TEXT,  -- 實作上犯的錯（off-by-one, overflow, 初始化…）
    transcript       TEXT,  -- 與 AI 訪談的紀錄
    created_at       TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS tags (
    problem_id INTEGER REFERENCES problems(id),
    tag        TEXT,
    source     TEXT DEFAULT 'llm'   -- llm / user / judge
);
CREATE TABLE IF NOT EXISTS cards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER REFERENCES problems(id),
    trigger    TEXT,   -- 「看到 ___ 的時候」
    action     TEXT,   -- 「想到 ___」
    interval   REAL DEFAULT 1,     -- 間隔天數（簡化版 SM-2）
    due        TEXT DEFAULT (date('now', 'localtime'))
);
