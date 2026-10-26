"""第一項「編組狀況」的專用畫面:分隊只填進退管理機制說明,其餘由系統核對或業務科登錄。"""
import pandas as pd
import streamlit as st

from utils import db, drive, rubric, scoring
from views import components as ui


def _valid_link(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://")


def _staffing_metrics(u: dict):
    ratio = u["headcount"] / u["authorized"] if u["authorized"] else None
    if u.get("source") == "sheet":
        st.caption("資料來源:專長資料庫試算表(總清冊與編制表),不含顧問,約每 10 分鐘更新一次。")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("編制人數", u["authorized"] or "—")
    c2.metric("現有人數(不含顧問)", u["headcount"] if u["authorized"] else "—")
    c3.metric("編組達成率", "—" if ratio is None else f"{ratio:.0%}")
    c4.metric("平均年齡", "—" if not u["avg_age"] else f"{u['avg_age']:.1f}")
    pts = scoring.staffing_bonus(u)
    if not u["authorized"] or not u["avg_age"]:
        st.caption("尚無系統資料,待專長資料庫串接或業務科登錄後自動計算。")
    elif pts:
        st.success(f"符合加分條件,加 {pts:g} 分")
    else:
        st.caption("未達加分條件(需編組達編制 90% 以上,且平均年齡 42 歲以下)。")


def status_table(unit: str, source: str):
    """第一項每個小點的目前評分狀況:評核重點、由誰核對、目前狀況與得分。"""
    u = db.get_unit(unit)
    data = scoring.staffing_data(u)
    cfg = rubric.load()["item1"]
    entries = scoring.collect_entries(unit, source)
    a1, a2 = scoring.subpoint_rows(rubric.item("一"), entries, u, source)
    n_sys = len(data["age_outside_rows"]) if data["source"] == "sheet" else None

    if not a1["provisional"]:
        s1 = f"業務科已登錄 {a1['qty']:g} 人"
    elif n_sys is None:
        s1 = "尚未取得專長資料庫資料"
    elif n_sys:
        s1 = f"系統核對 {n_sys} 人不符,待業務科確認(先行試算)"
    else:
        s1 = "系統核對:全部符合"
    s2 = f"業務科已登錄 {a2['qty']:g} 處" if a2["qty"] else "尚無扣分紀錄"
    pts = scoring.staffing_bonus(data)
    ratio = data["headcount"] / data["authorized"] if data["authorized"] else None
    s3 = ("尚無系統資料" if ratio is None or not data["avg_age"]
          else f"達成率 {ratio:.0%},平均 {data['avg_age']:.1f} 歲")
    mgmt = scoring.mgmt_bonus(u)
    s4 = ("分隊已填寫說明" if u["mgmt_text"] else "分隊尚未填寫說明") + ";" + \
         ("業務科已評分" if u["mgmt_scored"] else "業務科尚未評分")

    st.dataframe(pd.DataFrame([
        {"小點": a1["name"], "評核重點": f"年齡須在 {cfg['age_min']}~{cfg['age_max']} 歲,不符每人扣 0.5 分",
         "配分": f"{a1['points']} 分", "核對方式": "專長資料庫自動核對,業務科確認", "目前狀況": s1,
         "目前得分": f"{a1['score']:g} / {a1['points']}"},
        {"小點": a2["name"], "評核重點": "新進義消或退隊異動資料須於當月更新,未更新每處扣 0.5 分",
         "配分": f"{a2['points']} 分", "核對方式": "業務科抽查,業務科填寫", "目前狀況": s2,
         "目前得分": f"{a2['score']:g} / {a2['points']}"},
        {"小點": "3-(1) 編組人數加分", "評核重點": "編組達編制 90% 以上,平均年齡 40/41/42 歲以下加 1/0.8/0.6 分",
         "配分": "加分", "核對方式": "系統自動計算", "目前狀況": s3, "目前得分": f"+{pts:g}"},
        {"小點": "3-(2) 進退管理機制", "評核重點": f"管理規範、輔導汰換,最高加 {cfg['mgmt_max']} 分",
         "配分": f"加分(最高 {cfg['mgmt_max']})", "核對方式": "分隊提供說明,業務科給分", "目前狀況": s4,
         "目前得分": f"+{mgmt:g}"},
    ]), hide_index=True, width="stretch")
    res = scoring.unit_result(unit, source)
    st.caption(f"第一項目前得分 {res['scores']['一']:g} / 10,另加分 +{pts + mgmt:g}。"
               + ("業務科尚未確認的部分以系統試算,正式成績以業務科登錄為準。" if source != "review" else ""))


def _age_check(data: dict) -> int | None:
    """專長資料庫年齡核對:回傳年齡不在規定範圍的人數;無資料時回傳 None。"""
    cfg = rubric.load()["item1"]
    lo, hi = cfg["age_min"], cfg["age_max"]
    if data.get("source") != "sheet":
        st.caption("尚未取得專長資料庫資料,無法核對年齡。")
        return None
    rows = data["age_outside_rows"]
    if rows:
        st.warning(f"系統核對:編組人員(不含顧問)年齡不在 {lo}~{hi} 歲的有 {len(rows)} 人,"
                   f"位於專長資料庫總清冊第 {'、'.join(map(str, rows))} 列。請確認年齡或出生日期是否登錄正確。")
    else:
        st.success(f"系統核對:編組人員(不含顧問)年齡全部在 {lo}~{hi} 歲範圍內。")
    if data["age_at_max"]:
        st.caption(f"另有 {data['age_at_max']} 人剛好 {hi} 歲,依「{hi} 歲以下」視為符合,未計入。")
    return len(rows)


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面。"""
    u = db.get_unit(unit)
    data = scoring.staffing_data(u)
    st.markdown("##### 各小點評分狀況")
    status_table(unit, "self")
    st.markdown("##### 1、編組人員年齡 與 2、基本資料更新")
    st.info("第 1 點由義消專長資料庫直接核對,不用提供資料。第 2 點由本科抽查,新進義消或退隊異動資料請於每月 5 日前在專長資料庫更新,"
            "沒有按時更新的,每處扣 0.5 分(由業務科登錄)。")
    _age_check(data)

    st.markdown("##### 3、編組人數加分")
    st.markdown("**(1) 編組達編制 90% 以上且平均年齡達標:系統自動計算,不用填寫**")
    _staffing_metrics(data)

    st.markdown(f"**(2) 進退管理機制(最高加 {rubric.load()['item1']['mgmt_max']} 分)**")
    st.caption("請說明分隊的管理規範(內部管理方針、考核要點、激勵汰換措施)與輔導汰換的執行情形,"
               "並提供佐證資料夾連結,業務科會依方案、執行狀況及成效評斷給分。")
    text = st.text_area("文字說明", u["mgmt_text"], key=f"mgmt_text_{unit}", height=160, disabled=locked)
    default_link = u["mgmt_link"]
    if not default_link and drive.enabled():
        try:
            fid = drive.item_folder_id(unit, u["battalion"], "一")
            default_link = drive.folder_url(fid) if fid else ""
        except Exception:
            default_link = ""
    link = st.text_input("佐證資料夾連結(請確認連結已開放業務科檢視)", default_link, key=f"mgmt_link_{unit}",
                         disabled=locked, placeholder="https://drive.google.com/drive/folders/…")
    if st.button("儲存進退管理機制說明", key=f"mgmt_save_{unit}", type="primary", disabled=locked):
        if link.strip() and not _valid_link(link.strip()):
            st.error("連結必須以 https:// 開頭")
        else:
            db.update_unit(unit, mgmt_text=text.strip(), mgmt_link=link.strip())
            st.success("已儲存")
            st.rerun()
    st.caption(f"業務科評分:{scoring.mgmt_bonus(u):g} 分" if u["mgmt_scored"] else "業務科評分:尚未評分")


def review_panel(unit: str, user: dict):
    """業務科(可編輯)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    u = db.get_unit(unit)
    mgmt_max = rubric.load()["item1"]["mgmt_max"]

    st.markdown("##### 各小點評分狀況")
    status_table(unit, "review")
    st.markdown("##### 3-(1) 編組人數加分(系統自動計算)")
    data = scoring.staffing_data(u)
    authorized, headcount, avg_age = u["authorized"], u["headcount"], u["avg_age"]
    if data["source"] == "sheet":
        _staffing_metrics(data)
    else:
        st.warning("目前讀不到專長資料庫試算表的資料,改用業務科手動登錄的數字。")
        c1, c2, c3 = st.columns(3)
        authorized = c1.number_input("編制人數", min_value=0, step=1, value=int(u["authorized"]),
                                     key=f"auth_{unit}", disabled=not is_hq)
        headcount = c2.number_input("現有人數(不含顧問)", min_value=0, step=1, value=int(u["headcount"]),
                                    key=f"head_{unit}", disabled=not is_hq)
        avg_age = c3.number_input("平均年齡", min_value=0.0, max_value=100.0, step=0.1, value=float(u["avg_age"]),
                                  key=f"age_{unit}", disabled=not is_hq)
        _staffing_metrics({**u, "authorized": authorized, "headcount": headcount, "avg_age": avg_age,
                           "source": "manual"})

    st.markdown("##### 3-(2) 進退管理機制(分隊提供說明,業務科給分)")
    st.markdown("**分隊說明**")
    st.write(u["mgmt_text"] or "(分隊尚未填寫)")
    if u["mgmt_link"] and _valid_link(u["mgmt_link"]):
        st.link_button("開啟分隊提供的佐證資料夾", u["mgmt_link"])
    elif u["mgmt_link"]:
        st.warning("分隊填寫的連結格式不正確")
    else:
        st.caption("分隊尚未提供佐證資料夾連結")
    mgmt_score = st.number_input(f"業務科給分(0 ~ {mgmt_max} 分)", min_value=0.0, max_value=float(mgmt_max), step=0.5,
                                 value=min(float(u["mgmt_score"] or 0), float(mgmt_max)),
                                 key=f"mgmt_score_{unit}", disabled=not is_hq)
    if is_hq and st.button("儲存進退管理評分", key=f"item1_save_{unit}", type="primary"):
        if data["source"] == "manual" and headcount > authorized > 0:
            st.error("現有人數不可大於編制人數")
        else:
            db.update_unit(unit, authorized=int(authorized), headcount=int(headcount),
                           avg_age=float(avg_age), mgmt_score=float(mgmt_score), mgmt_scored=1)
            st.success("已儲存")
            st.rerun()
    elif not is_hq:
        st.caption("這兩項由業務科登錄,大隊僅供檢視。")

    st.markdown("##### 1、2 扣分登錄(業務科填寫,未填寫則不扣分)")
    n = _age_check(data)
    st.caption("評核表規定「派任時未屆齡而於任期中屆齡者不扣分」,系統無法判斷,請確認例外後再登錄人數。")
    if is_hq and n:
        if st.button(f"以系統核對結果填入年齡扣分({n} 人)", key=f"fill_age_{unit}"):
            others = [{"code": e["code"], "qty": e["qty"], "note": e["note"]}
                      for e in db.get_entries(unit, "review", "一") if e["code"] != "A1"]
            db.replace_entries(unit, "一", "review",
                               [{"code": "A1", "qty": n, "note": f"系統核對年齡不在 {rubric.load()['item1']['age_min']}~{rubric.load()['item1']['age_max']} 歲"}] + others,
                               user["account"])
            st.rerun()
    ui.entry_editor(unit, "一", "review", user["account"], editable=is_hq)
