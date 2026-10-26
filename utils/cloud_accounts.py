"""與義消專長資料庫共用帳號:直接讀 Google 試算表「系統帳號備份」,不在本系統另存密碼。

每次登入都讀最新內容(快取 60 秒),所以對方系統新增帳號、改密碼、停用,這裡約一分鐘內同步。
需要在 secrets 設定 GOOGLE_SERVICE_ACCOUNT、ACCOUNT_SHEET_ID,並把該試算表以「檢視者」共用給服務帳戶。
"""
import json
from pathlib import Path

import streamlit as st

from utils import db, hashing

TAB = "系統帳號備份"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ALIAS_PATH = Path(__file__).resolve().parent.parent / "data" / "unit_alias.json"
COLUMNS = {"帳號": "account", "所屬單位": "org", "角色": "role", "顯示名稱": "display",
           "狀態": "status", "密碼雜湊": "hash", "密碼鹽值": "salt"}


def _conf() -> tuple[dict | None, str | None, str | None]:
    try:
        info = st.secrets.get("GOOGLE_SERVICE_ACCOUNT")
        sheet = st.secrets.get("ACCOUNT_SHEET_ID")
        scheme = st.secrets.get("ACCOUNT_HASH_SCHEME")
    except Exception:
        return None, None, None
    if not info or not sheet:
        return None, None, None
    return (json.loads(info) if isinstance(info, str) else dict(info)), str(sheet), scheme


def enabled() -> bool:
    return _conf()[1] is not None


def _alias() -> dict:
    return json.loads(ALIAS_PATH.read_text(encoding="utf-8"))


@st.cache_data(ttl=60, show_spinner=False)
def fetch_accounts() -> dict[str, dict]:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    info, sheet, _ = _conf()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    rows = svc.spreadsheets().values().get(spreadsheetId=sheet, range=f"'{TAB}'!A1:H").execute().get("values", [])
    if not rows:
        return {}
    idx = {COLUMNS[h]: i for i, h in enumerate(rows[0]) if h in COLUMNS}
    out = {}
    for r in rows[1:]:
        rec = {k: (r[i].strip() if i < len(r) else "") for k, i in idx.items()}
        if rec.get("account"):
            out[rec["account"]] = rec
    return out


def to_user(rec: dict) -> tuple[dict | None, str]:
    """把雲端帳號對應成本系統的角色與分隊。"""
    alias = _alias()
    account, org = rec["account"], rec["org"]
    if account in alias["admin_accounts"]:
        return {"account": account, "role": "hq", "unit": None, "units": [], "battalion": None}, ""
    if org in alias.get("excluded", []):
        return None, "此單位不在本次評核範圍"
    if org in alias["battalions"]:
        b = alias["battalions"][org]
        return {"account": account, "role": "battalion", "unit": None, "units": [], "battalion": b}, ""
    if org in alias["units"]:
        units = [u for u in alias["units"][org] if db.get_unit(u)]
        if units:
            b = db.get_unit(units[0])["battalion"]
            return {"account": account, "role": "unit", "unit": units[0], "units": units, "battalion": b}, ""
    return None, f"帳號所屬單位「{org}」尚未對應到評核分隊,請聯絡管理員"


def check(account: str, password: str) -> tuple[dict | None, str]:
    _, _, scheme = _conf()
    try:
        rec = fetch_accounts().get(account)
    except Exception as e:
        return None, f"無法讀取雲端帳號資料:{e}"
    if not rec or rec.get("status") != "啟用" or not rec.get("hash") or not rec.get("salt"):
        return None, "帳號或密碼錯誤"
    try:
        ok = hashing.verify(password, rec["salt"], rec["hash"], scheme)
    except KeyError:
        return None, "系統設定錯誤:ACCOUNT_HASH_SCHEME 不是有效的雜湊方式"
    if not ok:
        return None, "帳號或密碼錯誤"
    return to_user(rec)
