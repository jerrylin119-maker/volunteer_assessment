"""評核登錄(大隊、業務科):檢視分隊佐證、登錄複評結果。"""
import pandas as pd
import streamlit as st

from utils import db, rubric, scoring
from views import components as ui
from views import item1, item2, item3, item4, item5, item6, item7, item8


def render(user: dict):
    st.title("評核登錄")
    battalion = None if user["role"] == "hq" else user["battalion"]
    units = db.list_units(battalion)
    if not units:
        st.info("尚無分隊資料。業務科可在「帳號管理」新增分隊。")
        return
    names = [u["name"] for u in units]
    # 業務科看得到所有大隊,標示大隊名稱方便辨識;大隊帳號只看得到自己的分隊,直接顯示分隊名稱就好
    label = (lambda n: f"{n}({db.get_unit(n)['battalion']})") if user["role"] == "hq" else (lambda n: n)
    unit = st.selectbox("受評分隊", names, format_func=label)
    info = db.get_unit(unit)
    who = user["account"]

    c1, c2, c3 = st.columns(3)
    c1.metric("自評試算", f"{scoring.unit_result(unit, 'self')['total']:.1f}")
    c2.metric("複評目前", f"{scoring.unit_result(unit, 'review')['total']:.1f}")
    c3.metric("狀態", "已完成" if info["review_done"] else "進行中")

    with st.expander("基本資料與完成狀態", expanded=False):
        done = st.toggle("複評完成(完成後分隊資料鎖定,並計入大隊成績)", value=bool(info["review_done"]),
                         key=f"done_{unit}")
        if st.button("儲存", key=f"save_unit_{unit}"):
            db.update_unit(unit, review_done=int(done))
            st.success("已儲存")
            st.rerun()
        st.caption(f"承辦人:{info['applicant'] or '未填'}  單位主管:{info['supervisor'] or '未填'}")
        st.caption("全年度爭取經費改在「六、全年度爭取經費情形」分頁逐筆登錄,見下方。")

    tabs = st.tabs([f"{it['id']} {it['name']}" for it in rubric.items()])
    for tab, it in zip(tabs, rubric.items()):
        with tab:
            with st.expander("評核標準"):
                st.write(it["standard"])
            ui.evidence_panel(unit, it["id"], who, can_edit=False)
            st.divider()
            selfs = db.get_entries(unit, "self", it["id"])
            if selfs:
                st.markdown("**分隊自評登錄**")
                st.dataframe(pd.DataFrame([{"代碼": e["code"], "內容": (rubric.code(e["code"]) or {}).get("text", ""),
                                            "數量": e["qty"], "說明": e["note"]} for e in selfs]),
                             hide_index=True, width="stretch")
                if st.button("以自評為複評起始值", key=f"copy_{unit}_{it['id']}"):
                    db.replace_entries(unit, it["id"], "review",
                                       [{"code": e["code"], "qty": e["qty"], "note": e["note"]} for e in selfs], who)
                    st.rerun()
            if it["id"] == "一":
                item1.review_panel(unit, user)
            elif it["id"] == "二":
                item2.review_panel(unit, user)
            elif it["id"] == "三":
                item3.review_panel(unit, user)
            elif it["id"] == "四":
                item4.review_panel(unit, user)
            elif it["id"] == "五":
                item5.review_panel(unit, user)
            elif it["id"] == "六":
                item6.review_panel(unit, user)
            elif it["id"] == "七":
                item7.review_panel(unit, user)
            elif it["id"] == "八":
                item8.review_panel(unit, user)
            else:
                ui.entry_editor(unit, it["id"], "review", who)

    st.divider()
    st.subheader("複評成績明細")
    st.dataframe(ui.result_table(unit, "review"), hide_index=True, width="stretch")
