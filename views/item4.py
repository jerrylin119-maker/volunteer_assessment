"""第四項「協勤情形」(10 分)。依分隊類型(救護/救災)顯示對應的檢附規定,
分隊勾選「資料已檢附齊全」直接生效給分(未勾選系統自動扣 2 分);
業務科只需確認有沒有個別缺失並登錄(每處缺失扣 0.5 分),不需要再手動確認檢附與否。
第 3 點(協勤民力系統登錄)由業務科抽檢給分,沒有獨立的分隊勾選項,查有缺失一併登錄。"""
import streamlit as st

from utils import db, scoring
from views import components as ui

ITEM = "四"


def _duty_type(unit: str) -> str:
    return "救護義消" if "救護" in unit else "救災義消"


def _requirement_text(unit: str) -> str:
    if _duty_type(unit) == "救護義消":
        return ("每位救護義消本年度應排定至少 72 小時以上協勤工作,完成者須檢附每月協勤績效表、"
               "出入登記簿或簽到表(須掃描);未檢附扣 2 分,每處缺失扣 0.5 分。")
    return ("協助消防人員執行救災、重大案件救護等勤務者,須檢附每月協勤績效表、出入登記簿或簽到表"
            "(須掃描)或臺東義消 APP 線上報到紀錄、每件勤務佐證照片 4 張;未檢附扣 2 分,每處缺失扣 0.5 分。")


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:依分隊類型顯示對應規定,勾選後直接生效(不扣那 2 分)。"""
    dtype = _duty_type(unit)
    info = db.get_unit(unit)
    st.markdown(f"##### {dtype}協勤情形")
    st.write(_requirement_text(unit))
    st.caption("勾選後立即生效,不需業務科另外確認;業務科審核資料時如發現個別缺失,仍會另外扣分。")
    checked = st.checkbox(f"本分隊本年度{dtype}協勤佐證資料均已完整檢附",
                          value=bool(info["duty_declared"]), key=f"duty_{unit}", disabled=locked)
    note = st.text_input("補充說明(選填,例如哪個月份、哪位隊員)", info["duty_declared_note"],
                         key=f"dutynote_{unit}", disabled=locked)
    if st.button("儲存", key=f"dutysave_{unit}", disabled=locked):
        db.update_unit(unit, duty_declared=int(checked), duty_declared_note=note)
        st.success("已儲存")
        st.rerun()
    if checked:
        st.success("已勾選,本項不扣「未檢附」的 2 分。")
    else:
        st.warning("尚未勾選,系統依規定先扣「未檢附」的 2 分;勾選並儲存後立即恢復。")
    st.divider()
    st.markdown("##### 協勤民力系統登錄情形")
    st.caption("上述協勤資料須詳實登錄至協勤民力系統,本項由業務科抽檢給分,不需分隊另外填報。")
    st.divider()
    res = scoring.unit_result(unit, "self")
    st.caption(f"第四項目前得分 {res['scores'][ITEM]:g} / 10。")
    ui.entry_editor(unit, ITEM, "self", who, editable=not locked)


def review_panel(unit: str, user: dict):
    """業務科(確認有無個別缺失並登錄)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    dtype = _duty_type(unit)
    info = db.get_unit(unit)
    st.markdown(f"##### 分隊自我宣告({dtype})")
    if info["duty_declared"]:
        st.success("分隊已勾選「資料已完整檢附」,已直接生效,不扣「未檢附」的 2 分。")
    else:
        st.warning("分隊尚未勾選,系統已自動扣「未檢附」的 2 分。")
    if info["duty_declared_note"]:
        st.caption(f"分隊補充說明:{info['duty_declared_note']}")
    st.caption("業務科只需核對佐證資料與協勤民力系統登錄情形,確認有沒有個別缺失,有的話在下方登錄(每處扣 0.5 分)。")
    st.divider()
    ui.entry_editor(unit, ITEM, "review", user["account"], editable=is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
