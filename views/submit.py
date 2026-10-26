"""分隊填報:依評核項次上傳佐證資料、登錄自評缺失。"""
import streamlit as st

from utils import db, rubric, scoring
from views import components as ui
from views import item1, item2, item3, item4, item5, item6, item7, item8


def render(user: dict):
    units = user.get("units") or [user["unit"]]
    unit = units[0] if len(units) == 1 else st.selectbox("填報分隊", units)
    info = db.get_unit(unit)
    st.title(f"{unit} 評核資料填報")
    st.caption(f"{rubric.load()['title']}。資料隨時可補充或修改,評核人員會看到最新內容。")

    with st.expander("📖 填寫說明(點此展開 / 收合)", expanded=True):
        st.markdown("""
1. 資料在評核期限前可以隨時填寫、隨時修改。
2. 佐證資料(簽到表、照片、統計表等)請直接上傳到各項目的雲端資料夾(每個項目都有「開啟此項目的雲端資料夾」按鈕),本系統不經手檔案,無法在這裡上傳。
3. 每個項目下方都有「評核標準」可以展開查看完整規定。
4. 只要看到輸入框、勾選框或清單旁邊有「儲存」或「新增」按鈕,填完**一定要按下去才會存檔**;畫面上純粹顯示文字或數字的地方(例如評核標準、系統自動算出的分數),不用按儲存。
5. 自評完成後會出現一份自評分數表供參考,正式評核成績視業務科複評結果而定。

有問題請聯絡業務科。
""")

    res = scoring.unit_result(unit, "self")
    c1, c2 = st.columns(2)
    c1.metric("自評試算總分(僅供參考)", f"{res['total']:.1f}")
    c2.metric("複評狀態", "已完成" if info["review_done"] else "進行中")

    with st.expander("承辦人與單位主管"):
        a = st.text_input("承辦人", info["applicant"], key=f"applicant_{unit}")
        s = st.text_input("單位主管", info["supervisor"], key=f"supervisor_{unit}")
        if st.button("儲存", key=f"save_people_{unit}"):
            db.update_unit(unit, applicant=a, supervisor=s)
            st.success("已儲存")

    locked = bool(info["review_done"])
    tabs = st.tabs([f"{it['id']} {it['name']}" for it in rubric.items()])
    for tab, it in zip(tabs, rubric.items()):
        with tab:
            st.subheader(f"{it['id']}、{it['name']}" + (f"({it['points']} 分)" if it["points"] else "(加分項目)"))
            with st.expander("評核標準", expanded=False):
                st.write(it["standard"])
            ui.evidence_panel(unit, it["id"], user["account"], can_edit=not locked)
            st.divider()
            if it["id"] == "一":
                item1.unit_panel(unit, user["account"], locked)
            elif it["id"] == "二":
                item2.unit_panel(unit, user["account"], locked)
            elif it["id"] == "三":
                item3.unit_panel(unit, user["account"], locked)
            elif it["id"] == "四":
                item4.unit_panel(unit, user["account"], locked)
            elif it["id"] == "五":
                item5.unit_panel(unit, user["account"], locked)
            elif it["id"] == "六":
                item6.unit_panel(unit, user["account"], locked)
            elif it["id"] == "七":
                item7.unit_panel(unit, user["account"], locked)
            elif it["id"] == "八":
                item8.unit_panel(unit, user["account"], locked)
            else:
                ui.entry_editor(unit, it["id"], "self", user["account"], not locked)
            if locked:
                st.caption("複評已完成,資料已鎖定。如需修改請聯絡評核人員。")

    st.divider()
    st.subheader("自評試算明細")
    st.dataframe(ui.result_table(unit, "self"), hide_index=True, width="stretch")
