"""從專長資料庫試算表取得各分隊的編制人數、現有人數、平均年齡(第一項「編組狀況」自動計算用)。

只讀必要欄位:總清冊的「單位」「職稱」「年紀」,與編制表的「編制員額(不含顧問)」,
不讀姓名、身分證字號、地址等個人資料。人數與平均年齡都不含職稱為「顧問」的人員。
"""
import json

import streamlit as st

from utils import rubric

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ADVISOR = "顧問"
ROSTER_TAB, STAFFING_TAB = "總清冊", "編制表"


def _conf() -> tuple[dict | None, str | None]:
    try:
        info = st.secrets.get("GOOGLE_SERVICE_ACCOUNT")
        sheet = st.secrets.get("ROSTER_SHEET_ID") or st.secrets.get("ACCOUNT_SHEET_ID")
    except Exception:
        return None, None
    if not info or not sheet:
        return None, None
    return (json.loads(info) if isinstance(info, str) else dict(info)), str(sheet)


def enabled() -> bool:
    return _conf()[1] is not None


def sheet_name(unit: str) -> str:
    """本系統分隊名稱對應到試算表的單位名稱(救災分隊在表中不加「救災」,救護分隊則保留)。"""
    return unit.replace("救災義消分隊", "義消分隊")


@st.cache_data(ttl=600, show_spinner=False)
def _fetch() -> dict[str, dict]:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    info, sheet = _conf()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    ranges = [f"'{STAFFING_TAB}'!A2:B", f"'{ROSTER_TAB}'!C3:D", f"'{ROSTER_TAB}'!L3:L"]
    got = svc.spreadsheets().values().batchGet(
        spreadsheetId=sheet, ranges=ranges, valueRenderOption="UNFORMATTED_VALUE").execute()["valueRanges"]
    staffing, people, ages = (g.get("values", []) for g in got)

    cfg = rubric.load()["item1"]
    age_min, age_max = cfg["age_min"], cfg["age_max"]  # 規定年齡範圍,含上下限

    def blank(authorized=0):
        return {"authorized": authorized, "headcount": 0, "age_sum": 0.0, "age_n": 0,
                "age_outside_rows": [], "age_at_max": 0}

    out: dict[str, dict] = {}
    for row in staffing:
        if len(row) > 1 and isinstance(row[1], (int, float)):
            out[str(row[0]).strip()] = blank(int(row[1]))
    for i, row in enumerate(people):
        unit = str(row[0]).strip() if row else ""
        title = str(row[1]).strip() if len(row) > 1 else ""
        if not unit or title == ADVISOR:
            continue
        rec = out.setdefault(unit, blank())
        rec["headcount"] += 1
        age = ages[i][0] if i < len(ages) and ages[i] else None
        if isinstance(age, (int, float)) and age > 0:
            rec["age_sum"] += age
            rec["age_n"] += 1
            if age < age_min or age > age_max:
                rec["age_outside_rows"].append(i + 3)  # 總清冊的列號(資料從第 3 列開始),不含個資
            if age == age_max:
                rec["age_at_max"] += 1
    return {u: {"authorized": r["authorized"], "headcount": r["headcount"],
                "avg_age": round(r["age_sum"] / r["age_n"], 2) if r["age_n"] else 0.0,
                "age_outside_rows": r["age_outside_rows"], "age_at_max": r["age_at_max"]}
            for u, r in out.items()}


def stats(unit: str) -> dict | None:
    """回傳 {authorized, headcount, avg_age};未設定、讀取失敗或表中查無此單位時回傳 None。"""
    if not enabled():
        return None
    try:
        return _fetch().get(sheet_name(unit))
    except Exception:
        return None
