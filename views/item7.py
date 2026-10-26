"""第七項「監督管理情形(財務管理)」(3 分)。分隊勾選「公佈資料齊全」直接生效給分
(未勾選系統自動扣完 3 分,跟第四、五項同一套做法)。業務科核對後如仍有個別缺失,可登錄每處扣 0.5 分。"""
import streamlit as st

from utils import db, scoring
from views import components as ui

ITEM = "七"


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:勾選後立即生效。"""
    st.markdown("##### 財務公佈情形")
    st.write("分隊經費支出須每 3 個月公佈(以會議或張貼公布欄方式,且有資料可循,如照片電子檔)。")
    st.caption("勾選後立即生效,不需業務科另外確認;業務科核對資料時如仍發現個別缺失,仍會另外扣分。")
    info = db.get_unit(unit)
    checked = st.checkbox("本分隊每 3 個月財務公佈資料齊全(會議紀錄或公布欄照片)",
                          value=bool(info["finance_declared"]), key=f"fin_{unit}", disabled=locked)
    note = st.text_input("補充說明(選填)", info["finance_declared_note"], key=f"finnote_{unit}", disabled=locked)
    if st.button("儲存", key=f"finsave_{unit}", disabled=locked):
        db.update_unit(unit, finance_declared=int(checked), finance_declared_note=note)
        st.success("已儲存")
        st.rerun()
    if checked:
        st.success("已勾選,本項不扣這 3 分。")
    else:
        st.warning("尚未勾選,系統依規定先扣這 3 分;勾選並儲存後立即恢復。")
    st.divider()
    res = scoring.unit_result(unit, "self")
    st.caption(f"第七項目前得分 {res['scores'][ITEM]:g} / 3。")
    ui.entry_editor(unit, ITEM, "self", who, editable=not locked)


def review_panel(unit: str, user: dict):
    """業務科(核對是否齊全、登錄個別缺失)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    info = db.get_unit(unit)
    if info["finance_declared"]:
        st.success("分隊已勾選「資料齊全」,已直接生效,不扣這 3 分。")
    else:
        st.warning("分隊尚未勾選,系統已自動扣這 3 分。")
    if info["finance_declared_note"]:
        st.caption(info["finance_declared_note"])
    st.caption("請核對佐證資料是否齊全,如發現個別缺失(即使已勾選),請在下方登錄每處扣 0.5 分。")
    st.divider()
    ui.entry_editor(unit, ITEM, "review", user["account"], editable=is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
