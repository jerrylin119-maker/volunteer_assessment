"""第三項「訓練情形」:(一)專業訓練 10 分、(二)常年訓練 10 分。
分隊依類別填報訓練時數、勾選已完成常年訓練的月份;系統統計結果供業務科參考,
正式扣分仍由業務科依佐證資料登錄(系統只呈現統計,不自動扣分)。"""
import pandas as pd
import streamlit as st

from utils import db, drive, rubric
from views import components as ui

ITEM = "三"
MONTHS = list(range(1, 13))


def _subfolder_link(unit: str, sub_key: str, sub_name: str, keywords: list[str], can_create: bool):
    """顯示「專業訓練」或「常年訓練」子資料夾的連結,找不到時依 can_create 決定要不要自動建立。"""
    if not drive.enabled():
        return
    battalion = (db.get_unit(unit) or {}).get("battalion", "")
    try:
        fid = drive.subfolder_id(unit, battalion, ITEM, sub_key, sub_name, keywords, create=can_create)
    except Exception as e:
        st.warning(f"無法連線 Google 雲端:{e}")
        return
    if fid:
        st.link_button(f"📁 開啟「{sub_name}」資料夾", drive.folder_url(fid))
    else:
        st.caption(f"尚未找到「{sub_name}」資料夾。")


def _required_category(unit: str) -> tuple[str, str]:
    """回傳(必修類別, 顯示名稱)。分隊名稱含「救護」須達緊急救護類,其餘須達火災搶救類。"""
    if "救護" in unit:
        return "緊急救護類", "緊急救護訓練"
    return "火災搶救類", "火搶訓練"


def _prof_summary(unit: str) -> dict:
    required_cat, required_label = _required_category(unit)
    by_cat: dict[str, float] = {}
    for r in db.get_training_prof(unit):
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["hours"]
    required_hours = by_cat.get(required_cat, 0)
    other_hours = sum(h for cat, h in by_cat.items() if cat != required_cat)
    return {"required_label": required_label, "required_hours": required_hours, "other_hours": other_hours,
            "total": required_hours + other_hours}


def _prof_editor(unit: str, who: str, editable: bool):
    cfg = rubric.load()["training"]
    rows = db.get_training_prof(unit)
    df = pd.DataFrame([{"類別": r["category"], "時數": r["hours"], "說明": r["note"]} for r in rows],
                      columns=["類別", "時數", "說明"])
    edited = st.data_editor(
        df, num_rows="dynamic" if editable else "fixed", disabled=not editable,
        hide_index=True, width="stretch", key=f"profedit_{unit}",
        column_config={
            "類別": st.column_config.SelectboxColumn("訓練類別", options=cfg["categories"], required=True),
            "時數": st.column_config.NumberColumn("時數", min_value=0.0, step=0.5, format="%g", required=True),
            "說明": st.column_config.TextColumn("說明(例如辦理日期)", width="medium"),
        })
    if editable and st.button("儲存專業訓練時數", key=f"profsave_{unit}", type="primary"):
        rows_out = []
        for _, r in edited.iterrows():
            if pd.isna(r["類別"]) or pd.isna(r["時數"]):
                continue
            rows_out.append({"category": r["類別"], "hours": r["時數"],
                             "note": "" if pd.isna(r["說明"]) else str(r["說明"])})
        db.replace_training_prof(unit, rows_out, who)
        st.success("已儲存")
        st.rerun()
    s = _prof_summary(unit)
    st.info(f"專業訓練完成{s['required_label']} {s['required_hours']:g} 小時,"
            f"其餘訓練 {s['other_hours']:g} 小時(合計 {s['total']:g} 小時)。")
    if s["required_hours"] < cfg["required_hours"]:
        st.warning(f"{s['required_label']}尚未達 {cfg['required_hours']} 小時。")
    if s["total"] < cfg["total_hours"]:
        st.warning(f"全年度專業訓練總時數尚未達 {cfg['total_hours']} 小時。")


def _months_editor(unit: str, editable: bool):
    current = set(db.get_training_months(unit))
    cols = st.columns(6)
    picked = set()
    for i, m in enumerate(MONTHS):
        with cols[i % 6]:
            if st.checkbox(f"{m} 月", value=m in current, key=f"mon_{unit}_{m}", disabled=not editable):
                picked.add(m)
    if editable and st.button("儲存常年訓練月份", key=f"monsave_{unit}", type="primary"):
        db.set_training_months(unit, sorted(picked))
        st.success("已儲存")
        st.rerun()
    n = len(current)
    detail = "、".join(f"{m} 月" for m in sorted(current))
    st.info(f"已完成本年度 {n} 個月份的常年訓練" + (f"({detail})" if detail else "") + "。")
    if n < 12:
        st.warning(f"尚有 {12 - n} 個月份未勾選完成。")


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:(一)專業訓練時數登錄、(二)常年訓練完成月份勾選。"""
    st.markdown("##### (一) 專業訓練")
    st.caption("請選擇訓練類別與時數,系統會自動加總。佐證資料(訓練計畫、統計總表、課程表、相片、簽到表)"
               "請上傳到下方的「專業訓練」資料夾。")
    _subfolder_link(unit, "prof", "專業訓練", ["專業訓練", "專業"], can_create=not locked)
    _prof_editor(unit, who, not locked)
    st.divider()
    st.markdown("##### (二) 常年訓練")
    st.caption("請勾選本年度已完成常年訓練的月份。佐證資料請上傳到下方的「常年訓練」資料夾。")
    _subfolder_link(unit, "annual", "常年訓練", ["常年訓練", "常年"], can_create=not locked)
    _months_editor(unit, not locked)
    st.divider()
    ui.subpoint_table(ITEM, unit, "self")


def review_panel(unit: str, user: dict):
    """業務科(登錄正式扣分)與大隊(唯讀)的複評畫面:先看分隊填報的統計,再登錄正式缺失。"""
    is_hq = user["role"] == "hq"
    st.markdown("##### 分隊填報的訓練統計(唯讀)")
    s = _prof_summary(unit)
    st.write(f"專業訓練完成{s['required_label']} {s['required_hours']:g} 小時,"
            f"其餘訓練 {s['other_hours']:g} 小時(合計 {s['total']:g} 小時)。")
    _subfolder_link(unit, "prof", "專業訓練", ["專業訓練", "專業"], can_create=False)
    months = db.get_training_months(unit)
    detail = "、".join(f"{m} 月" for m in months)
    st.write(f"已完成本年度 {len(months)} 個月份的常年訓練" + (f"({detail})" if detail else "") + "。")
    _subfolder_link(unit, "annual", "常年訓練", ["常年訓練", "常年"], can_create=False)
    st.divider()
    st.markdown("##### 評核重點與目前扣分")
    ui.subpoint_table(ITEM, unit, "review")
    st.markdown("##### 缺失登錄(業務科填寫,未填寫則不扣分)")
    ui.entry_editor(unit, ITEM, "review", user["account"], editable=is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
