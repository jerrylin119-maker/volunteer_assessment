"""成績總表(大隊、業務科):分隊成績、大隊成績、Excel 匯出。"""
import io

import pandas as pd
import streamlit as st

from utils import db, rubric, scoring


def _unit_frame(units: list[dict]) -> pd.DataFrame:
    rows = []
    for u in units:
        res = scoring.unit_result(u["name"], "review")
        done = bool(u["review_done"])
        row = {"大隊": u["battalion"], "分隊": u["name"], "複評狀態": "已完成" if done else "進行中",
               "自評試算": round(scoring.unit_result(u["name"], "self")["total"], 2)}
        for it in rubric.items():
            if it["id"] != "八":
                row[f"{it['id']} {it['name']}"] = round(res["scores"][it["id"]], 2) if done else None
        row["加分"] = round(res["bonus"], 2) if done else None
        row["分隊總分"] = round(res["total"], 2) if done else None
        rows.append(row)
    return pd.DataFrame(rows)


def _battalion_frame(battalions: list[str]) -> pd.DataFrame:
    topics = rubric.load()["hq_topics"]
    rows = []
    for b in battalions:
        r = scoring.battalion_result(b)
        row = {"大隊": b, "分隊數": r["unit_count"], "複評完成": r["done_count"],
               "分隊平均": None if r["avg"] is None else round(r["avg"], 2),
               "分隊成績加權": None if r["weighted"] is None else round(r["weighted"], 2)}
        for t, s in zip(topics, r["topic_scores"]):
            row[t] = round(s, 2)
        row["業務科配合事項"] = round(r["hq_total"], 2)
        row["大隊總分"] = None if r["total"] is None else round(r["total"], 2)
        rows.append(row)
    return pd.DataFrame(rows)


def render(user: dict):
    st.title("成績總表")
    battalion = None if user["role"] == "hq" else user["battalion"]
    units = db.list_units(battalion)
    battalions = sorted({u["battalion"] for u in units})
    if not units:
        st.info("尚無分隊資料。")
        return
    cfg = rubric.load()

    st.subheader("分隊成績")
    st.caption("正式成績只在「複評完成」後顯示;自評試算僅供參考。")
    uf = _unit_frame(units)
    st.dataframe(uf, hide_index=True, width="stretch")

    st.subheader("大隊成績")
    w = int(cfg["battalion_weight"] * 100)
    st.caption(f"大隊總分 = 轄下已完成複評分隊的算術平均 × {w}% + 業務科配合事項"
               f"(每項 = 無缺失件數 ÷ 總送件數 × {cfg['hq_item_max']},三項合計最高 "
               f"{cfg['hq_item_max'] * len(cfg['hq_topics'])} 分)。")
    bf = _battalion_frame(battalions)
    st.dataframe(bf, hide_index=True, width="stretch")

    if user["role"] == "hq":
        st.subheader("業務科配合事項登錄")
        b = st.selectbox("大隊", battalions, key="hq_battalion")
        cur = db.get_hq_scores(b)
        edit = pd.DataFrame([{"審查項目": t, "年度總送件數": cur.get(i, {}).get("total", 0),
                              "送件完全無缺失件數": cur.get(i, {}).get("ok", 0)}
                             for i, t in enumerate(cfg["hq_topics"])])
        edited = st.data_editor(edit, hide_index=True, width="stretch", disabled=["審查項目"],
                                key=f"hq_edit_{b}",
                                column_config={
                                    "年度總送件數": st.column_config.NumberColumn(min_value=0, step=1),
                                    "送件完全無缺失件數": st.column_config.NumberColumn(min_value=0, step=1)})
        if st.button("儲存業務科登錄", type="primary"):
            if (edited["送件完全無缺失件數"] > edited["年度總送件數"]).any():
                st.error("無缺失件數不可大於總送件數")
            else:
                for i, r in edited.iterrows():
                    db.set_hq_score(b, int(i), int(r["年度總送件數"]), int(r["送件完全無缺失件數"]))
                st.success("已儲存")
                st.rerun()

    buf = io.BytesIO()
    detail = [{"分隊": u["name"], "代碼": e["code"], "內容": (rubric.code(e["code"]) or {}).get("text", ""),
               "數量": e["qty"], "來源": "複評" if e["source"] == "review" else "自評",
               "說明": e["note"], "登錄人": e["who"], "時間": e["created_at"]}
              for u in units for s in ("self", "review") for e in db.get_entries(u["name"], s)]
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        uf.to_excel(xw, sheet_name="分隊成績", index=False)
        bf.to_excel(xw, sheet_name="大隊成績", index=False)
        pd.DataFrame(detail, columns=["分隊", "代碼", "內容", "數量", "來源", "說明", "登錄人", "時間"]
                     ).to_excel(xw, sheet_name="登錄明細", index=False)
    st.download_button("下載 Excel", buf.getvalue(), file_name="義消評核成績.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
