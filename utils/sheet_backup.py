"""把評核資料備份到 Google 試算表(每個分隊一個分頁),並在本機資料庫被清空時自動還原。

這份試算表是備份,不是分隊填報的介面:每次有分隊、業務科的資料變動,系統會把該分隊的
完整狀態整頁覆蓋寫入對應分頁,所以人工在試算表上改的內容會被下一次寫入蓋掉。
技術上以 A1 存一份 JSON(程式讀寫用),下面是給人看的表格。
"""
import json
from datetime import datetime

import streamlit as st

from utils import db, rubric

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PROFILE_FIELDS = ["applicant", "supervisor", "funding", "review_done", "authorized", "headcount", "avg_age",
                  "mgmt_text", "mgmt_link", "mgmt_score", "mgmt_scored", "training_months",
                  "duty_declared", "duty_declared_note",
                  "equip_roster_declared", "equip_roster_note", "equip_check_declared", "equip_check_note",
                  "finance_declared", "finance_declared_note", "h2_text", "h2_rejected"]
PROFILE_LABELS = ["承辦人", "單位主管", "全年度爭取經費(元)", "複評完成", "編制人數(手動)", "現有人數(手動)",
                  "平均年齡(手動)", "進退管理機制說明", "進退管理機制佐證連結", "進退管理機制業務科評分",
                  "進退管理機制業務科已評分", "常年訓練已完成月份", "第四項協勤資料自我宣告已檢附",
                  "第四項自我宣告補充說明", "第五項裝備造冊自我宣告", "第五項裝備造冊補充說明",
                  "第五項個人裝備年度檢查自我宣告", "第五項個人裝備年度檢查補充說明",
                  "第七項財務公佈自我宣告", "第七項自我宣告補充說明",
                  "第八項2救護技能競賽參賽項目", "第八項2業務科已取消"]


def _conf() -> tuple[dict | None, str | None]:
    try:
        info = st.secrets.get("GOOGLE_SERVICE_ACCOUNT")
        sheet = st.secrets.get("BACKUP_SHEET_ID")
    except Exception:
        return None, None
    if not info or not sheet:
        return None, None
    return (json.loads(info) if isinstance(info, str) else dict(info)), str(sheet)


def enabled() -> bool:
    return _conf()[1] is not None


@st.cache_resource
def _service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    info, _ = _conf()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _tab(name: str) -> str:
    # Google 試算表分頁名稱含這些字元或超過 100 字時無效;分隊名稱目前都安全,這裡僅作保險
    safe = "".join(c for c in name if c not in "[]*?/\\:")[:95]
    return safe or "分隊"


# ---- 整理單一分隊的完整狀態 ----
def snapshot(unit: str) -> dict:
    u = db.get_unit(unit)
    entries = db.get_entries(unit, "self") + db.get_entries(unit, "review")
    notes = {it["id"]: db.get_note(unit, it["id"]) for it in rubric.items()}
    evidence = db.list_evidence(unit)
    return {"unit": u, "entries": entries, "notes": {k: v for k, v in notes.items() if v}, "evidence": evidence,
            "training_prof": db.get_training_prof(unit), "creative_cases": db.get_creative_cases(unit),
            "funding_cases": db.get_funding_cases(unit),
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _readable_rows(snap: dict) -> list[list]:
    u = snap["unit"] or {}
    rows = [[f"{u.get('name', '')}({u.get('battalion', '')}) 資料備份"], [f"備份時間:{snap['saved_at']}"], []]
    rows.append(["基本資料"])
    for field, label in zip(PROFILE_FIELDS, PROFILE_LABELS):
        rows.append([label, u.get(field, "")])
    rows += [[], ["第三項專業訓練時數"], ["類別", "時數", "說明", "登錄人", "時間"]]
    for r in snap.get("training_prof") or []:
        rows.append([r["category"], r["hours"], r["note"], r["who"], r["created_at"]])
    rows += [[], ["第六項爭取經費案件"], ["案件說明", "金額", "業務科已確認", "登錄人", "時間"]]
    for r in snap.get("funding_cases") or []:
        rows.append([r["description"], r["amount"], "是" if r["confirmed"] else "否", r["who"], r["created_at"]])
    rows += [[], ["第八項 3 建設性作為"], ["說明", "業務科已確認可分享", "登錄人", "時間"]]
    for r in snap.get("creative_cases") or []:
        rows.append([r["description"], "是" if r["confirmed"] else "否", r["who"], r["created_at"]])
    rows += [[], ["評核登錄(扣分/加分)"], ["來源", "項次", "代碼", "內容", "數量", "說明", "登錄人", "時間"]]
    for e in snap["entries"]:
        code = rubric.code(e["code"]) or {}
        rows.append(["複評" if e["source"] == "review" else "分隊自評", e["item"], e["code"],
                     code.get("text", ""), e["qty"], e["note"], e["who"], e["created_at"]])
    rows += [[], ["分隊說明"], ["項次", "說明文字", "更新人", "更新時間"]]
    for item_id, n in snap["notes"].items():
        rows.append([item_id, n["text"], n["updated_by"], n["updated_at"]])
    rows += [[], ["佐證檔案清單"], ["項次", "檔名", "連結", "說明", "上傳人", "上傳時間"]]
    for e in snap["evidence"]:
        rows.append([e["item"], e["filename"], e["drive_url"] or "(本機檔案)", e["note"], e["uploaded_by"], e["uploaded_at"]])
    return rows


def write_unit(unit: str):
    """把某分隊的完整狀態整頁覆蓋寫入它的備份分頁。失敗時不中斷畫面,只記錄警告。"""
    if not enabled():
        return
    try:
        _, sheet = _conf()
        snap = snapshot(unit)
        tab = _tab(unit)
        rows = [["__JSON__", json.dumps(snap, ensure_ascii=False, default=str)]] + _readable_rows(snap)
        svc = _service()
        svc.spreadsheets().values().clear(spreadsheetId=sheet, range=f"'{tab}'!A1:Z2000").execute()
        svc.spreadsheets().values().update(spreadsheetId=sheet, range=f"'{tab}'!A1", valueInputOption="RAW",
                                           body={"values": rows}).execute()
    except Exception as e:
        st.warning(f"備份到雲端試算表失敗,這次的修改仍已存在本機資料庫:{e}")


def read_unit(unit: str) -> dict | None:
    if not enabled():
        return None
    try:
        _, sheet = _conf()
        r = _service().spreadsheets().values().get(spreadsheetId=sheet, range=f"'{_tab(unit)}'!A1:B1").execute()
        rows = r.get("values", [])
        if not rows or rows[0][0] != "__JSON__":
            return None
        return json.loads(rows[0][1])
    except Exception:
        return None


def _local_is_blank(unit: str) -> bool:
    u = db.get_unit(unit)
    if not u:
        return True
    touched = any(u.get(f) for f in ("applicant", "supervisor", "funding", "mgmt_text", "mgmt_link", "mgmt_score",
                                     "training_months", "duty_declared", "duty_declared_note",
                                     "equip_roster_declared", "equip_check_declared",
                                     "finance_declared", "h2_text"))
    return not touched and not db.get_entries(unit, "self") and not db.get_entries(unit, "review") \
        and not db.list_evidence(unit) and not db.get_training_prof(unit) and not db.get_creative_cases(unit) \
        and not db.get_funding_cases(unit) \
        and not any(db.get_note(unit, it["id"]) for it in rubric.items())


def restore_unit_if_blank(unit: str):
    """本機這個分隊完全沒有資料(例如主機重啟清空了檔案)時,從備份還原;本機已有資料則不覆蓋。"""
    if not _local_is_blank(unit):
        return
    snap = read_unit(unit)
    if not snap:
        return
    u = snap.get("unit") or {}
    if any(u.get(f) for f in PROFILE_FIELDS):
        db.update_unit(unit, **{f: u[f] for f in PROFILE_FIELDS if f in u})
    for source in ("self", "review"):
        rows = [{"code": e["code"], "qty": e["qty"], "note": e["note"]}
                for e in snap["entries"] if e["source"] == source]
        by_item: dict[str, list] = {}
        for e, row in zip([e for e in snap["entries"] if e["source"] == source], rows):
            by_item.setdefault(e["item"], []).append(row)
        for item_id, item_rows in by_item.items():
            db.replace_entries(unit, item_id, source, item_rows, "還原備份")
    for item_id, n in (snap.get("notes") or {}).items():
        db.set_note(unit, item_id, n["text"], n["updated_by"])
    if snap.get("training_prof"):
        db.replace_training_prof(
            unit, [{"category": r["category"], "hours": r["hours"], "note": r["note"]}
                  for r in snap["training_prof"]], "還原備份")
    for r in snap.get("creative_cases") or []:
        db.add_creative_case(unit, r["description"], "還原備份")
        if r["confirmed"]:
            cases = db.get_creative_cases(unit)
            if cases:
                db.set_creative_case_confirmed(cases[-1]["id"], True)
    for r in snap.get("funding_cases") or []:
        db.add_funding_case(unit, r["description"], r["amount"], "還原備份")
        if r["confirmed"]:
            cases = db.get_funding_cases(unit)
            if cases:
                db.set_funding_case_confirmed(cases[-1]["id"], True)
    # 佐證檔案:只還原 Drive 連結(本機檔案遺失時無法復原,僅還原中繼資料供人工核對)
    for e in snap.get("evidence") or []:
        if e.get("drive_url"):
            db.add_evidence(unit, e["item"], e["filename"], "", e["note"], e["uploaded_by"], e["drive_url"])


def restore_all():
    if not enabled():
        return
    for u in db.list_units():
        try:
            restore_unit_if_blank(u["name"])
        except Exception:
            pass  # 還原失敗不影響網站啟動,該分隊維持空白狀態,等下次有人儲存資料時會重新備份


@st.cache_resource
def ensure_restored() -> bool:
    """每個網站執行程序只做一次還原(st.cache_resource 的快取會跨多次互動保留,直到網站重啟)。"""
    restore_all()
    restore_hq_if_blank()
    return True


# ---- 業務科配合事項(大隊層級)----
def write_hq():
    if not enabled():
        return
    try:
        _, sheet = _conf()
        topics = rubric.load()["hq_topics"]
        rows = [["大隊", "審查項目", "年度總送件數", "送件完全無缺失件數"]]
        for b in sorted({u["battalion"] for u in db.list_units()}):
            hq = db.get_hq_scores(b)
            for i, t in enumerate(topics):
                h = hq.get(i, {"total": 0, "ok": 0})
                rows.append([b, t, h["total"], h["ok"]])
        svc = _service()
        svc.spreadsheets().values().clear(spreadsheetId=sheet, range="'業務科配合事項'!A1:Z2000").execute()
        svc.spreadsheets().values().update(spreadsheetId=sheet, range="'業務科配合事項'!A1", valueInputOption="RAW",
                                           body={"values": rows}).execute()
    except Exception as e:
        st.warning(f"業務科配合事項備份失敗:{e}")


def restore_hq_if_blank():
    if not enabled():
        return
    try:
        battalions = sorted({u["battalion"] for u in db.list_units()})
        if any(db.get_hq_scores(b) for b in battalions):
            return  # 本機已有資料,不覆蓋
        _, sheet = _conf()
        r = _service().spreadsheets().values().get(spreadsheetId=sheet, range="'業務科配合事項'!A2:D").execute()
        topics = rubric.load()["hq_topics"]
        for row in r.get("values", []):
            if len(row) < 4:
                continue
            b, topic, total, ok = row[0], row[1], row[2], row[3]
            if topic in topics:
                db.set_hq_score(b, topics.index(topic), int(total or 0), int(ok or 0))
    except Exception:
        pass
