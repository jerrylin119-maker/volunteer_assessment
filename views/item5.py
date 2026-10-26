"""第五項「裝備器材維護情形」(10 分):裝備器材造冊管理 5 分、個人裝備年度檢查紀錄 5 分。
分隊各自勾選是否已完成,勾選後直接生效給分(未勾選系統自動扣完該小點 5 分,跟第四項同一套做法)。
業務科核對佐證資料,確認是否翔實,如發現個別缺失仍可登錄(每處扣 0.5 分),不需要再手動確認「是否已完成」本身。"""
import streamlit as st

from utils import db, scoring
from views import components as ui

ITEM = "五"


def _declare_block(unit: str, label: str, declared_field: str, note_field: str, locked: bool, points: int):
    info = db.get_unit(unit)
    checked = st.checkbox(label, value=bool(info[declared_field]), key=f"{declared_field}_{unit}", disabled=locked)
    note = st.text_input("補充說明(選填)", info[note_field], key=f"{note_field}_{unit}", disabled=locked)
    if st.button("儲存", key=f"{declared_field}_save_{unit}", disabled=locked):
        db.update_unit(unit, **{declared_field: int(checked), note_field: note})
        st.success("已儲存")
        st.rerun()
    if checked:
        st.success(f"已勾選,本小點不扣這 {points} 分。")
    else:
        st.warning(f"尚未勾選,系統依規定先扣這 {points} 分;勾選並儲存後立即恢復。")


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:兩個小點各自勾選是否已完成,勾選後立即生效。"""
    st.markdown("##### 1、裝備器材造冊管理(5 分)")
    st.caption("勾選後立即生效,不需業務科另外確認;業務科核對資料時如發現個別缺失,仍會另外扣分。")
    _declare_block(unit, "本分隊裝備器材造冊管理(含領用簽收表)已完成", "equip_roster_declared", "equip_roster_note",
                   locked, 5)
    st.divider()
    st.markdown("##### 2、個人裝備年度檢查紀錄(5 分)")
    st.caption("勾選後立即生效,不需業務科另外確認;業務科核對資料時如發現個別缺失,仍會另外扣分。")
    _declare_block(unit, "本分隊個人裝備年度檢查紀錄已完成並掃描存檔", "equip_check_declared", "equip_check_note",
                   locked, 5)
    st.divider()
    res = scoring.unit_result(unit, "self")
    st.caption(f"第五項目前得分 {res['scores'][ITEM]:g} / 10。")
    ui.entry_editor(unit, ITEM, "self", who, editable=not locked)


def review_panel(unit: str, user: dict):
    """業務科(核對是否翔實、登錄個別缺失)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    info = db.get_unit(unit)
    st.markdown("##### 分隊自我宣告")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**1、裝備器材造冊管理**")
        if info["equip_roster_declared"]:
            st.success("已勾選,不扣這 5 分。")
        else:
            st.warning("尚未勾選,系統已自動扣這 5 分。")
        if info["equip_roster_note"]:
            st.caption(info["equip_roster_note"])
    with c2:
        st.write("**2、個人裝備年度檢查紀錄**")
        if info["equip_check_declared"]:
            st.success("已勾選,不扣這 5 分。")
        else:
            st.warning("尚未勾選,系統已自動扣這 5 分。")
        if info["equip_check_note"]:
            st.caption(info["equip_check_note"])
    st.caption("請核對佐證資料是否翔實,如發現個別缺失(即使已勾選),請在下方登錄每處扣 0.5 分。")
    st.divider()
    ui.entry_editor(unit, ITEM, "review", user["account"], editable=is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
