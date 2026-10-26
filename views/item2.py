"""第二項「協勤民力資訊管理系統建置情形」:先呈現評核重點與目前扣分,下面是分隊提供說明的地方。"""
import streamlit as st

from utils import rubric
from views import components as ui

ITEM = "二"


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:上方已有民力系統匯出檔案的上傳區,這裡是評核重點與補充說明。"""
    st.markdown("##### 評核重點")
    st.write(rubric.item(ITEM)["standard"])
    ui.subpoint_table(ITEM, unit, "self")
    st.caption("系統分析匯出檔案自動核對的功能尚在開發,目前由業務科依上傳的資料人工核對、登錄缺失。")
    st.markdown("##### 補充說明")
    ui.note_box(unit, ITEM, who, locked, "說明(例如資料建置進度、缺失原因、已改善的情形)",
                "儲存後會顯示在下方,業務科與大隊評核時看得到。")


def review_panel(unit: str, user: dict):
    """業務科(可登錄缺失)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    st.markdown("##### 評核重點與目前扣分")
    ui.subpoint_table(ITEM, unit, "review")
    ui.note_view(unit, ITEM)
    st.markdown("##### 缺失登錄(業務科填寫,未填寫則不扣分)")
    ui.entry_editor(unit, ITEM, "review", user["account"], editable=is_hq)
    if not is_hq:
        st.caption("這一項由業務科登錄,大隊僅供檢視。")
