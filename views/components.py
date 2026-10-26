"""分隊填報與評核登錄共用的畫面元件。"""
import pandas as pd
import streamlit as st

from utils import db, drive, rubric, scoring

SOURCE_LABEL = {"self": "分隊自評", "review": "複評"}


def evidence_panel(unit: str, item_id: str, who: str, can_edit: bool):
    """佐證資料:系統不經手檔案,只提供 Drive 資料夾連結,請直接在 Drive 裡上傳與管理。"""
    it = rubric.item(item_id)
    st.markdown("**應備佐證資料**")
    for e in it["evidence"]:
        st.markdown(f"- {e}")

    if not drive.enabled():
        st.info("尚未設定 Google 雲端串接,請聯絡管理員。")
        return

    battalion = (db.get_unit(unit) or {}).get("battalion", "")
    try:
        fid = drive.item_folder_id(unit, battalion, item_id, create=can_edit)
    except Exception as e:  # 網路或權限問題不應讓整頁壞掉
        st.warning(f"無法連線 Google 雲端:{e}")
        return
    if not fid:
        st.caption("尚未找到對應的雲端資料夾。")
        return

    st.link_button("📁 開啟此項目的雲端資料夾(請直接在這裡上傳佐證資料)", drive.folder_url(fid), type="primary")
    with st.expander("查看資料夾內目前有哪些檔案"):
        try:
            files = drive.list_files(fid)
        except Exception as e:
            st.caption(f"無法讀取資料夾內容:{e}")
            return
        if not files:
            st.caption("這個資料夾目前還沒有檔案。")
        for f in files:
            st.markdown(f"- [{f['name']}]({f.get('webViewLink', drive.folder_url(fid))})")


def entry_editor(unit: str, item_id: str, source: str, who: str, editable: bool = True):
    """缺失與加分登錄表:每列選代碼、填數量,儲存後自動算分。"""
    cs = [c for c in rubric.codes(item_id) if c.get("who") != "system"]  # system:系統自動計算,不給人工登錄
    if source == "self":  # 標示 who=hq 的扣分項目只有業務科能登錄,分隊自評不顯示
        cs = [c for c in cs if c.get("who") != "hq"]
    if not cs:
        return
    label = {c["code"]: rubric.code_label(c) for c in cs}
    by_label = {v: k for k, v in label.items()}
    existing = db.get_entries(unit, source, item_id)
    df = pd.DataFrame(
        [{"項目": label.get(e["code"], e["code"]), "數量": e["qty"], "說明": e["note"]} for e in existing],
        columns=["項目", "數量", "說明"])
    df["數量"] = df["數量"].astype(float)
    st.markdown(f"**{SOURCE_LABEL[source]}:缺失與加分登錄**")
    edited = st.data_editor(
        df, num_rows="dynamic" if editable else "fixed", disabled=not editable,
        width="stretch", hide_index=True, key=f"ed_{source}_{unit}_{item_id}",
        column_config={
            "項目": st.column_config.SelectboxColumn("扣分/加分項目", options=list(label.values()),
                                                      required=True, width="large"),
            "數量": st.column_config.NumberColumn("數量", min_value=0.0, step=1.0, format="%g", required=True),
            "說明": st.column_config.TextColumn("說明(缺失內容、日期等)", width="medium"),
        })
    if editable and st.button("儲存登錄", key=f"save_{source}_{unit}_{item_id}", type="primary"):
        rows = []
        for _, r in edited.iterrows():
            if pd.isna(r["項目"]) or pd.isna(r["數量"]) or r["數量"] <= 0:
                continue
            rows.append({"code": by_label[r["項目"]], "qty": r["數量"],
                         "note": "" if pd.isna(r["說明"]) else str(r["說明"])})
        db.replace_entries(unit, item_id, source, rows, who)
        st.success("已儲存")
        st.rerun()
    res = scoring.unit_result(unit, source)
    it = rubric.item(item_id)
    if item_id != "八":
        st.caption(f"本項目前得分 {res['scores'][item_id]:.2f} / {it['points']} 分"
                   f"(已扣 {res['deducted'][item_id]:.2f} 分)")


def note_box(unit: str, item_id: str, who: str, locked: bool, label: str, help_text: str = ""):
    """分隊的文字說明:儲存後直接顯示在頁面上,業務科與大隊在評核畫面也看得到。"""
    note = db.get_note(unit, item_id)
    text = st.text_area(label, note["text"] if note else "", key=f"note_{unit}_{item_id}", height=140,
                        disabled=locked, help=help_text or None)
    if st.button("儲存說明", key=f"notesave_{unit}_{item_id}", disabled=locked):
        db.set_note(unit, item_id, text, who)
        st.success("已儲存")
        st.rerun()
    note_view(unit, item_id, heading="已提供的說明")


def note_view(unit: str, item_id: str, heading: str = "分隊提供的說明"):
    note = db.get_note(unit, item_id)
    st.markdown(f"**{heading}**")
    if not note:
        st.caption("尚未提供說明")
        return
    with st.container(border=True):
        st.write(note["text"])
    st.caption(f"{note['updated_by']} 於 {note['updated_at']} 更新")


def subpoint_table(item_id: str, unit: str, source: str):
    """依評核表的小點分組,顯示扣分標準、業務科目前登錄的缺失與累計扣分(配分有拆分時含各小點得分)。"""
    it = rubric.item(item_id)
    entries = [e for e in scoring.collect_entries(unit, source) if e["item"] == item_id]
    split = bool(it.get("subpoints")) and all(sp["points"] is not None for sp in it["subpoints"])
    rows = []
    for sp in it.get("subpoints") or []:
        codes = [rubric.code(c) for c in sp["codes"]]
        mine = [e for e in entries if e["code"] in sp["codes"]]
        deduct = sum(scoring.entry_points(e) for e in mine)
        standard = ";".join(f"{c['text']}(每{c['unit']}扣 {c['unit_score']:g} 分"
                            f"{'、至多 ' + format(c['cap'], 'g') + ' 分' if c['cap'] else ''})" for c in codes)
        row = {"評核重點": sp["name"], "扣分標準": standard,
               "業務科核對登錄": f"{len(mine)} 筆缺失" if mine else "尚無缺失紀錄",
               "目前扣分": f"-{deduct:g}" if deduct else "0"}
        if split:
            row["目前得分"] = f"{max(0, sp['points'] - deduct):g} / {sp['points']}"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    res = scoring.unit_result(unit, source)
    st.caption(f"第{item_id}項目前得分 {res['scores'][item_id]:g} / {it['points']}(扣 {res['deducted'][item_id]:g} 分)。"
               "由業務科依佐證資料登錄缺失,沒有登錄就不扣分。")


def result_table(unit: str, source: str) -> pd.DataFrame:
    res = scoring.unit_result(unit, source)
    rows = [{"項次": it["id"], "評核項目": it["name"], "配分": it["points"], "得分": round(res["scores"][it["id"]], 2)}
            for it in rubric.items() if it["id"] != "八"]
    rows.append({"項次": "八", "評核項目": "加分合計", "配分": None, "得分": round(res["bonus"], 2)})
    rows.append({"項次": "", "評核項目": "總分", "配分": None, "得分": round(res["total"], 2)})
    return pd.DataFrame(rows)
