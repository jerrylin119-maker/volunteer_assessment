"""第八項「分隊平均分數加分」(無固定配分,加總計入年度總分)。
1、複訓到訓比例加分(最高 2 分):業務科直接核給人數與分數,分隊不開放填寫。
2、救護技能競賽(加 1 分):分隊填寫參賽項目,填寫後直接生效加 1 分,業務科審核後可取消。
3、建設性作為(每案加 2 分):分隊填寫多筆構想,業務科逐筆確認可分享者才給分。"""
import streamlit as st

from utils import db, scoring
from views import components as ui

ITEM = "八"


def _section1_readonly(unit: str):
    st.markdown("##### 1、複訓到訓比例加分(最高 2 分)")
    st.caption("積極參加本局辦理火搶義消、先鋒義消及後勤義消複訓,依到訓比例加分,由業務科核給人數及分數,分隊不需填寫。")
    entries = [e for e in db.get_entries(unit, "review") if e["item"] == ITEM and e["code"] == "H1"]
    total = sum(scoring.entry_points(e) for e in entries)
    st.write(f"業務科目前核給:{total:g} 分")


def _section1_hq(unit: str, who: str):
    st.markdown("##### 1、複訓到訓比例加分(最高 2 分)")
    st.caption("積極參加本局辦理火搶義消、先鋒義消及後勤義消複訓,依到訓比例加分,請依到訓人數核給分數(最高 2 分)。")
    ui.entry_editor(unit, ITEM, "review", who)


def _section2(unit: str, is_hq: bool, editable: bool):
    st.markdown("##### 2、救護技能競賽(加 1 分)")
    info = db.get_unit(unit)
    if not is_hq:
        st.caption("參加全國或區域性救護技能競賽並組隊參加者,填寫參賽項目後直接加 1 分,業務科審核後可取消。")
        text = st.text_input("參賽項目(例如:115年全國救護技能競賽)", info["h2_text"],
                             key=f"h2_{unit}", disabled=not editable)
        if st.button("儲存", key=f"h2save_{unit}", disabled=not editable):
            db.update_unit(unit, h2_text=text)
            st.success("已儲存")
            st.rerun()
        if info["h2_text"]:
            if info["h2_rejected"]:
                st.warning("業務科審核後已取消此項加分,請確認資料或聯絡業務科。")
            else:
                st.success(f"已登錄「{info['h2_text']}」,加 1 分。")
        else:
            st.caption("尚未填寫。")
    else:
        if not info["h2_text"]:
            st.caption("分隊尚未填寫參賽項目。")
        else:
            st.write(f"分隊填寫:{info['h2_text']}")
            rejected = st.checkbox("審核後取消此項加分", value=bool(info["h2_rejected"]), key=f"h2rej_{unit}")
            if st.button("儲存審核結果", key=f"h2rejsave_{unit}"):
                db.update_unit(unit, h2_rejected=int(rejected))
                st.success("已儲存")
                st.rerun()


def _section3(unit: str, who: str, is_hq: bool, editable: bool):
    st.markdown("##### 3、建設性作為(每案加 2 分)")
    rows = db.get_creative_cases(unit)
    if not is_hq:
        st.caption("有創意建設性想法並實際運用於分隊業務推動者,請填寫說明;經業務科審核可分享給各分隊者,每案加 2 分。")
        for r in rows:
            c1, c2 = st.columns([5, 1])
            c1.write(("✅ " if r["confirmed"] else "⏳ ") + r["description"])
            if editable and not r["confirmed"] and c2.button("刪除", key=f"delcase_{r['id']}"):
                db.delete_creative_case(r["id"])
                st.rerun()
        new_text = st.text_input("新增一筆建設性作為說明", key=f"newcase_{unit}", disabled=not editable)
        if editable and st.button("新增", key=f"addcase_{unit}", disabled=not new_text.strip()):
            db.add_creative_case(unit, new_text.strip(), who)
            st.success("已新增")
            st.rerun()
        confirmed = sum(1 for r in rows if r["confirmed"])
        if confirmed:
            st.success(f"業務科已確認 {confirmed} 案,加 {confirmed * 2:g} 分。")
    else:
        if not rows:
            st.caption("分隊尚未填寫。")
        for r in rows:
            c1, c2 = st.columns([5, 1])
            c1.write(r["description"])
            new_val = c2.checkbox("可分享(+2分)", value=bool(r["confirmed"]), key=f"creative_confirm_{r['id']}")
            if new_val != bool(r["confirmed"]):
                db.set_creative_case_confirmed(r["id"], new_val)
                st.rerun()


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:1 唯讀、2 填一筆參賽項目、3 填多筆建設性作為。"""
    _section1_readonly(unit)
    st.divider()
    _section2(unit, False, not locked)
    st.divider()
    _section3(unit, who, False, not locked)


def review_panel(unit: str, user: dict):
    """業務科(三個小點都可操作)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    if is_hq:
        _section1_hq(unit, user["account"])
    else:
        _section1_readonly(unit)
    st.divider()
    _section2(unit, is_hq, is_hq)
    st.divider()
    _section3(unit, user["account"], is_hq, is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
