"""第九項「配合本局年度重大工作」:大隊評核項目。大隊帳號登入後的主畫面。"""
import pandas as pd
import streamlit as st

from utils import db, rubric, scoring


def render(user: dict):
    cfg = rubric.load()
    item = cfg["battalion_item"]
    if user["role"] == "hq":
        battalions = sorted({u["battalion"] for u in db.list_units()})
        if not battalions:
            st.info("尚無分隊資料。")
            return
        battalion = st.selectbox("大隊", battalions)
    else:
        battalion = user["battalion"]

    units = db.list_units(battalion)
    names = "、".join(u["name"] for u in units)
    res = scoring.battalion_result(battalion)
    weight = int(cfg["battalion_weight"] * 100)

    st.title(f"{battalion} 評核")
    st.subheader(f"{item['id']}、{item['name']}")
    with st.expander("評核標準"):
        st.write(item["standard"])

    c1, c2, c3 = st.columns(3)
    c1.metric("轄下分隊複評完成", f"{res['done_count']} / {res['unit_count']}")
    c2.metric(f"分隊成績加權({weight}%)", "—" if res["weighted"] is None else f"{res['weighted']:.2f}")
    c3.metric("大隊總分", "—" if res["total"] is None else f"{res['total']:.2f}")

    st.markdown(f"#### 1、分隊執行成效(佔總成績 {weight}%)")
    st.markdown(f"各義消分隊({names})")
    rows = []
    for u in units:
        r = scoring.unit_result(u["name"], "review") if u["review_done"] else None
        rows.append({"分隊": u["name"], "複評狀態": "已完成" if u["review_done"] else "進行中",
                     "分隊總分": None if r is None else round(r["total"], 2)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("只計入複評已完成的分隊;分隊平均 = 這些分隊總分的算術平均。"
               + ("" if res["avg"] is None else f" 目前平均 {res['avg']:.2f},加權後 {res['weighted']:.2f}。"))

    st.markdown(f"#### 2、業務科配合事項(佔總成績 {100 - weight}%)")
    hq = db.get_hq_scores(battalion)
    max_each = cfg["hq_item_max"]
    st.dataframe(pd.DataFrame([
        {"審查項目": t, "年度總送件數": hq.get(i, {}).get("total", 0),
         "送件完全無缺失件數": hq.get(i, {}).get("ok", 0), f"得分(滿分 {max_each})": round(res["topic_scores"][i], 2)}
        for i, t in enumerate(cfg["hq_topics"])]), hide_index=True, width="stretch")
    st.caption("這三項由業務科登錄,大隊只能檢視。"
               f"業務科配合事項合計 {res['hq_total']:.2f} 分(最高 {max_each * len(cfg['hq_topics'])} 分)。")
