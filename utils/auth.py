"""帳號驗證。之後要改用民力科核發的帳號,只需替換 verify() 與 create/reset 函式。"""
import csv
import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta

from utils import cloud_accounts, db

LOCKOUT_ENABLED = False  # 依使用者要求停用鎖定;失敗次數仍會記錄供日後查閱
MAX_FAILS = 5
LOCK_MINUTES = 10
INITIAL_FILE = db.DATA_DIR / "initial_accounts.csv"

ROLE_LABEL = {"unit": "分隊", "battalion": "大隊", "hq": "業務科"}
_UNITS_BY_BATTALION = {
    "臺東大隊": ["臺東救災義消分隊", "臺東救護義消分隊", "卑南救災義消分隊", "大豐救災義消分隊",
                 "豐田救災義消分隊", "南王救災義消分隊", "知本救災義消分隊", "知本救護義消分隊",
                 "特搜救災義消分隊", "綠島救災義消分隊", "蘭嶼救災義消分隊"],
    "大武大隊": ["大武救災義消分隊", "太麻里救災義消分隊", "大溪救災義消分隊", "達仁救災義消分隊",
                 "金峰救災義消分隊"],
    "關山大隊": ["池上救災義消分隊", "延平救災義消分隊", "海端義消分隊", "鹿野救災義消分隊", "關山救災義消分隊"],
    "成功大隊": ["成功救災義消分隊", "東河救災義消分隊", "長濱救災義消分隊"],
}
SEED_UNITS = [(b, u) for b, us in _UNITS_BY_BATTALION.items() for u in us]


def gen_password(n: int = 10) -> str:
    alphabet = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def set_account(account: str, password: str, role: str, unit: str | None = None,
                battalion: str | None = None):
    salt = secrets.token_hex(16)
    with db.get_conn() as c:
        c.execute(
            "INSERT INTO accounts(account,salt,pw_hash,role,unit,battalion) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(account) DO UPDATE SET salt=excluded.salt, pw_hash=excluded.pw_hash, "
            "role=excluded.role, unit=excluded.unit, battalion=excluded.battalion",
            (account, salt, _hash(password, salt), role, unit, battalion))


def reset_password(account: str) -> str:
    pw = gen_password()
    with db.get_conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE account=?", (account,)).fetchone()
        if not row:
            raise ValueError("查無此帳號")
        salt = secrets.token_hex(16)
        c.execute("UPDATE accounts SET salt=?, pw_hash=? WHERE account=?", (salt, _hash(pw, salt), account))
    return pw


def change_password(account: str, new_password: str):
    with db.get_conn() as c:
        salt = secrets.token_hex(16)
        c.execute("UPDATE accounts SET salt=?, pw_hash=? WHERE account=?",
                  (salt, _hash(new_password, salt), account))


def verify(account: str, password: str) -> tuple[dict | None, str]:
    if LOCKOUT_ENABLED:
        with db.get_conn() as c:
            fail = c.execute("SELECT * FROM login_fail WHERE account=?", (account,)).fetchone()
            if fail and fail["count"] >= MAX_FAILS:
                last = datetime.strptime(fail["last"], "%Y-%m-%d %H:%M:%S")
                if datetime.now() - last < timedelta(minutes=LOCK_MINUTES):
                    return None, f"登入失敗次數過多,請 {LOCK_MINUTES} 分鐘後再試"
    if cloud_accounts.enabled():  # 與義消專長資料庫共用帳號,不使用本機帳號
        user, msg = cloud_accounts.check(account, password)
        if user or msg == "此單位不在本次評核範圍":
            _clear_fail(account)
        elif msg == "帳號或密碼錯誤":  # 雲端讀取失敗、對照缺漏等系統問題不計入失敗次數
            _record_fail(account)
        return user, msg
    with db.get_conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE account=?", (account,)).fetchone()
    if row and hmac.compare_digest(_hash(password, row["salt"]), row["pw_hash"]):
        _clear_fail(account)
        return dict(row), ""
    _record_fail(account)
    return None, "帳號或密碼錯誤"


def _clear_fail(account: str):
    with db.get_conn() as c:
        c.execute("DELETE FROM login_fail WHERE account=?", (account,))


def _record_fail(account: str):
    with db.get_conn() as c:
        c.execute("INSERT INTO login_fail(account,count,last) VALUES (?,1,?) "
                  "ON CONFLICT(account) DO UPDATE SET count=count+1, last=excluded.last",
                  (account, db.now()))


def create_unit_account(unit: str, battalion: str) -> str:
    """建立分隊與其帳號(帳號名稱=分隊名稱),回傳初始密碼。"""
    db.add_unit(unit, battalion)
    pw = gen_password()
    set_account(unit, pw, "unit", unit=unit, battalion=battalion)
    return pw


def seed_if_empty():
    """第一次啟動:建立業務科帳號、關山大隊與其 5 個分隊帳號,初始密碼寫入 data/initial_accounts.csv。"""
    with db.get_conn() as c:
        if c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]:
            return
    rows = []
    pw = gen_password()
    set_account("hq", pw, "hq")
    rows.append(("hq", "業務科", pw))
    for battalion in sorted({b for b, _ in SEED_UNITS}):
        pw = gen_password()
        set_account(battalion, pw, "battalion", battalion=battalion)
        rows.append((battalion, "大隊", pw))
    for battalion, unit in SEED_UNITS:
        rows.append((unit, "分隊", create_unit_account(unit, battalion)))
    with open(INITIAL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["帳號", "角色", "初始密碼"])
        w.writerows(rows)
    INITIAL_FILE.chmod(0o600)
