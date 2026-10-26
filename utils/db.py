"""SQLite 儲存層:分隊、帳號、評核登錄(自評/複評)、佐證檔案、業務科配合事項。"""
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "assessment.db"
UPLOAD_DIR = DATA_DIR / "uploads"


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


UNIT_RENAMES = {"海端分隊": "海端義消分隊"}  # 舊名稱 → 新名稱,啟動時自動遷移已存的資料


def _migrate_unit_names(c):
    for old, new in UNIT_RENAMES.items():
        if c.execute("SELECT 1 FROM units WHERE name=?", (new,)).fetchone():
            continue  # 新名稱已存在,不重複遷移
        c.execute("UPDATE units SET name=? WHERE name=?", (new, old))
        c.execute("UPDATE accounts SET unit=? WHERE unit=?", (new, old))
        c.execute("UPDATE accounts SET account=? WHERE account=? AND role='unit'", (new, old))
        for table in ("entries", "evidence", "drive_map"):
            c.execute(f"UPDATE {table} SET unit=? WHERE unit=?", (new, old))


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS units (
            name TEXT PRIMARY KEY,
            battalion TEXT NOT NULL,
            applicant TEXT DEFAULT '',
            supervisor TEXT DEFAULT '',
            funding INTEGER DEFAULT 0,
            review_done INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS accounts (
            account TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            role TEXT NOT NULL,          -- unit / battalion / hq
            unit TEXT,
            battalion TEXT
        );
        CREATE TABLE IF NOT EXISTS login_fail (
            account TEXT PRIMARY KEY, count INTEGER, last TEXT
        );
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT NOT NULL,
            item TEXT NOT NULL,
            code TEXT NOT NULL,
            qty REAL NOT NULL,
            source TEXT NOT NULL,        -- self(分隊自評) / review(複評)
            note TEXT DEFAULT '',
            who TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT NOT NULL,
            item TEXT NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            note TEXT DEFAULT '',
            uploaded_by TEXT,
            uploaded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS hq_scores (
            battalion TEXT NOT NULL,
            topic INTEGER NOT NULL,
            total INTEGER DEFAULT 0,
            ok INTEGER DEFAULT 0,
            PRIMARY KEY (battalion, topic)
        );
        CREATE TABLE IF NOT EXISTS item_notes (
            unit TEXT NOT NULL,
            item TEXT NOT NULL,
            text TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT,
            PRIMARY KEY (unit, item)
        );
        CREATE TABLE IF NOT EXISTS training_prof (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT NOT NULL,
            category TEXT NOT NULL,
            hours REAL NOT NULL,
            note TEXT DEFAULT '',
            who TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS creative_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT NOT NULL,
            description TEXT NOT NULL,
            confirmed INTEGER DEFAULT 0,
            who TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS funding_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit TEXT NOT NULL,
            description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            confirmed INTEGER DEFAULT 0,
            who TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS drive_map (
            unit TEXT NOT NULL,
            item TEXT NOT NULL,
            folder_id TEXT NOT NULL,
            PRIMARY KEY (unit, item)
        );
        """)
        cols = [r[1] for r in c.execute("PRAGMA table_info(evidence)")]
        if "drive_url" not in cols:
            c.execute("ALTER TABLE evidence ADD COLUMN drive_url TEXT DEFAULT ''")
        unit_cols = [r[1] for r in c.execute("PRAGMA table_info(units)")]
        for col, ddl in [("authorized", "INTEGER DEFAULT 0"),    # 編制人數(不含顧問)
                         ("headcount", "INTEGER DEFAULT 0"),     # 現有編組人數(不含顧問)
                         ("avg_age", "REAL DEFAULT 0"),          # 平均年齡
                         ("mgmt_text", "TEXT DEFAULT ''"),       # 進退管理機制:分隊文字說明
                         ("mgmt_link", "TEXT DEFAULT ''"),       # 進退管理機制:佐證資料夾連結
                         ("mgmt_score", "REAL DEFAULT 0"),       # 進退管理機制:業務科給分
                         ("mgmt_scored", "INTEGER DEFAULT 0"),   # 業務科是否已評分(區分「尚未評分」與「評 0 分」)
                         ("training_months", "TEXT DEFAULT ''"),  # 第三項常年訓練:已完成的月份,逗號分隔如 "1,2,5"
                         ("duty_declared", "INTEGER DEFAULT 0"),  # 第四項:分隊自我宣告協勤佐證資料已完整檢附
                         ("duty_declared_note", "TEXT DEFAULT ''"),  # 第四項:分隊自我宣告的補充說明
                         ("equip_roster_declared", "INTEGER DEFAULT 0"),  # 第五項 1:分隊宣告是否已完成裝備造冊
                         ("equip_roster_note", "TEXT DEFAULT ''"),
                         ("equip_check_declared", "INTEGER DEFAULT 0"),  # 第五項 2:分隊宣告是否已完成個人裝備年度檢查
                         ("equip_check_note", "TEXT DEFAULT ''"),
                         ("finance_declared", "INTEGER DEFAULT 0"),  # 第七項:分隊宣告財務公佈資料是否齊全
                         ("finance_declared_note", "TEXT DEFAULT ''"),
                         ("h2_text", "TEXT DEFAULT ''"),  # 第八項 2:分隊填寫的救護技能競賽參賽項目
                         ("h2_rejected", "INTEGER DEFAULT 0")]:  # 第八項 2:業務科審核後取消此項加分
            if col not in unit_cols:
                c.execute(f"ALTER TABLE units ADD COLUMN {col} {ddl}")
        _migrate_unit_names(c)
    from utils import sheet_backup  # 延後匯入,避免與 sheet_backup 互相匯入時卡住
    sheet_backup.ensure_restored()


def _backup_unit(unit: str):
    from utils import sheet_backup
    sheet_backup.write_unit(unit)


def _backup_hq():
    from utils import sheet_backup
    sheet_backup.write_hq()


# ---- 分隊 ----
def list_units(battalion: str | None = None) -> list[dict]:
    with get_conn() as c:
        if battalion:
            rows = c.execute("SELECT * FROM units WHERE battalion=? ORDER BY name", (battalion,))
        else:
            rows = c.execute("SELECT * FROM units ORDER BY battalion, name")
        return [dict(r) for r in rows]


def get_unit(name: str) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM units WHERE name=?", (name,)).fetchone()
        return dict(r) if r else None


def add_unit(name: str, battalion: str):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO units(name, battalion) VALUES (?,?)", (name, battalion))


def update_unit(name: str, **fields):
    allowed = {"applicant", "supervisor", "funding", "review_done",
               "authorized", "headcount", "avg_age", "mgmt_text", "mgmt_link", "mgmt_score", "mgmt_scored",
               "training_months", "duty_declared", "duty_declared_note",
               "equip_roster_declared", "equip_roster_note", "equip_check_declared", "equip_check_note",
               "finance_declared", "finance_declared_note", "h2_text", "h2_rejected"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    with get_conn() as c:
        c.execute(f"UPDATE units SET {', '.join(k + '=?' for k in sets)} WHERE name=?",
                  (*sets.values(), name))
    _backup_unit(name)


# ---- 評核登錄 ----
def get_entries(unit: str, source: str, item: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM entries WHERE unit=? AND source=?", [unit, source]
    if item:
        q += " AND item=?"
        args.append(item)
    with get_conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id", args)]


def replace_entries(unit: str, item: str, source: str, rows: list[dict], who: str):
    """整批取代某分隊某項次的登錄(自評或複評),rows: [{code, qty, note}]。"""
    with get_conn() as c:
        c.execute("DELETE FROM entries WHERE unit=? AND item=? AND source=?", (unit, item, source))
        c.executemany(
            "INSERT INTO entries(unit,item,code,qty,source,note,who,created_at) VALUES (?,?,?,?,?,?,?,?)",
            [(unit, item, r["code"], float(r["qty"]), source, r.get("note") or "", who, now()) for r in rows],
        )
    _backup_unit(unit)


# ---- 第三項專業訓練:分隊填報的訓練類別與時數 ----
def get_training_prof(unit: str) -> list[dict]:
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM training_prof WHERE unit=? ORDER BY id", (unit,))]


def replace_training_prof(unit: str, rows: list[dict], who: str):
    """整批取代某分隊的專業訓練時數登錄,rows: [{category, hours, note}]。"""
    with get_conn() as c:
        c.execute("DELETE FROM training_prof WHERE unit=?", (unit,))
        c.executemany(
            "INSERT INTO training_prof(unit,category,hours,note,who,created_at) VALUES (?,?,?,?,?,?)",
            [(unit, r["category"], float(r["hours"]), r.get("note") or "", who, now()) for r in rows],
        )
    _backup_unit(unit)


# ---- 第六項:分隊逐筆填寫爭取經費案件與金額,業務科逐筆確認 ----
def get_funding_cases(unit: str) -> list[dict]:
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM funding_cases WHERE unit=? ORDER BY id", (unit,))]


def add_funding_case(unit: str, description: str, amount: int, who: str):
    with get_conn() as c:
        c.execute("INSERT INTO funding_cases(unit,description,amount,confirmed,who,created_at) VALUES (?,?,?,0,?,?)",
                  (unit, description, int(amount), who, now()))
    _backup_unit(unit)


def delete_funding_case(case_id: int):
    with get_conn() as c:
        row = c.execute("SELECT unit FROM funding_cases WHERE id=?", (case_id,)).fetchone()
        c.execute("DELETE FROM funding_cases WHERE id=?", (case_id,))
    if row:
        _backup_unit(row["unit"])


def set_funding_case_confirmed(case_id: int, confirmed: bool):
    with get_conn() as c:
        row = c.execute("SELECT unit FROM funding_cases WHERE id=?", (case_id,)).fetchone()
        c.execute("UPDATE funding_cases SET confirmed=? WHERE id=?", (int(confirmed), case_id))
    if row:
        _backup_unit(row["unit"])


# ---- 第八項 3:分隊填寫的建設性作為,業務科逐案確認 ----
def get_creative_cases(unit: str) -> list[dict]:
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM creative_cases WHERE unit=? ORDER BY id", (unit,))]


def add_creative_case(unit: str, description: str, who: str):
    with get_conn() as c:
        c.execute("INSERT INTO creative_cases(unit,description,confirmed,who,created_at) VALUES (?,?,0,?,?)",
                  (unit, description, who, now()))
    _backup_unit(unit)


def delete_creative_case(case_id: int):
    with get_conn() as c:
        row = c.execute("SELECT unit FROM creative_cases WHERE id=?", (case_id,)).fetchone()
        c.execute("DELETE FROM creative_cases WHERE id=?", (case_id,))
    if row:
        _backup_unit(row["unit"])


def set_creative_case_confirmed(case_id: int, confirmed: bool):
    with get_conn() as c:
        row = c.execute("SELECT unit FROM creative_cases WHERE id=?", (case_id,)).fetchone()
        c.execute("UPDATE creative_cases SET confirmed=? WHERE id=?", (int(confirmed), case_id))
    if row:
        _backup_unit(row["unit"])


def get_training_months(unit: str) -> list[int]:
    """第三項常年訓練:分隊勾選已完成訓練的月份(1~12)。"""
    u = get_unit(unit) or {}
    return sorted({int(x) for x in (u.get("training_months") or "").split(",") if x.strip().isdigit()})


def set_training_months(unit: str, months: list[int]):
    update_unit(unit, training_months=",".join(str(m) for m in sorted(set(months))))


# ---- 佐證檔案 ----
def add_evidence(unit: str, item: str, filename: str, path: str, note: str, who: str, drive_url: str = ""):
    """path 為本機相對路徑;檔案存在 Google Drive 時 path 留空、drive_url 為檔案連結。"""
    with get_conn() as c:
        c.execute("INSERT INTO evidence(unit,item,filename,path,note,uploaded_by,uploaded_at,drive_url) "
                  "VALUES (?,?,?,?,?,?,?,?)", (unit, item, filename, path, note, who, now(), drive_url))
    _backup_unit(unit)


def list_evidence(unit: str, item: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM evidence WHERE unit=?", [unit]
    if item:
        q += " AND item=?"
        args.append(item)
    with get_conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id DESC", args)]


def get_evidence(evidence_id: int) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone()
        return dict(r) if r else None


def delete_evidence(evidence_id: int):
    row = get_evidence(evidence_id)
    with get_conn() as c:
        c.execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
    if row:
        _backup_unit(row["unit"])


def evidence_counts() -> dict[tuple[str, str], int]:
    with get_conn() as c:
        return {(r["unit"], r["item"]): r["n"] for r in c.execute(
            "SELECT unit, item, COUNT(*) n FROM evidence GROUP BY unit, item")}


# ---- 分隊說明(各評核項次的文字說明) ----
def get_note(unit: str, item: str) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM item_notes WHERE unit=? AND item=?", (unit, item)).fetchone()
        return dict(r) if r else None


def set_note(unit: str, item: str, text: str, who: str):
    with get_conn() as c:
        if not text.strip():
            c.execute("DELETE FROM item_notes WHERE unit=? AND item=?", (unit, item))
        else:
            c.execute("INSERT INTO item_notes(unit,item,text,updated_by,updated_at) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(unit,item) DO UPDATE SET text=excluded.text, updated_by=excluded.updated_by, "
                      "updated_at=excluded.updated_at", (unit, item, text.strip(), who, now()))
    _backup_unit(unit)


# ---- 業務科配合事項 ----
def get_hq_scores(battalion: str) -> dict[int, dict]:
    with get_conn() as c:
        return {r["topic"]: dict(r) for r in c.execute(
            "SELECT * FROM hq_scores WHERE battalion=?", (battalion,))}


def set_hq_score(battalion: str, topic: int, total: int, ok: int):
    with get_conn() as c:
        c.execute("INSERT INTO hq_scores(battalion, topic, total, ok) VALUES (?,?,?,?) "
                  "ON CONFLICT(battalion, topic) DO UPDATE SET total=excluded.total, ok=excluded.ok",
                  (battalion, topic, total, ok))
    _backup_hq()
