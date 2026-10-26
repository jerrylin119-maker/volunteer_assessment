"""分隊重點優缺失表:彙整某分隊各項目得分、缺失清單與亮點,供業務科複評完成後列印或下載。"""
import streamlit as st

from utils import db, rubric, scoring


def _unit_report_markdown(unit: str) -> str:
    u = db.get_unit(unit)
    res = scoring.unit_result(unit, "review")
    lines = [f"# {unit}({u['battalion']}) 評核重點優缺失表", "",
             f"承辦人:{u['applicant'] or '未填'}  單位主管:{u['supervisor'] or '未填'}",
             f"複評狀態:{'已完成' if u['review_done'] else '進行中(以下為目前進度,非正式結果)'}",
             f"**年度總分:{res['total']:.1f}**", "", "## 各項目得分", "| 項次 | 項目 | 配分 | 得分 |",
             "| --- | --- | --- | --- |"]
    for it in rubric.items():
        if it["id"] == "八":
            continue
        lines.append(f"| {it['id']} | {it['name']} | {it['points']} | {res['scores'][it['id']]:.1f} |")
    lines.append(f"| 八 | 加分合計 | — | {res['bonus']:.1f} |")

    lines += ["", "## 缺失清單"]
    deducts = [e for e in db.get_entries(unit, "review") if (rubric.code(e["code"]) or {}).get("mode") == "扣分"]
    if not deducts:
        lines.append("本次複評無任何扣分紀錄。")
    else:
        by_item: dict[str, list] = {}
        for e in deducts:
            by_item.setdefault(e["item"], []).append(e)
        for item_id in sorted(by_item):
            it = rubric.item(item_id)
            lines.append(f"\n**{item_id}、{it['name']}**")
            for e in by_item[item_id]:
                code = rubric.code(e["code"]) or {}
                note = f"({e['note']})" if e["note"] else ""
                lines.append(f"- {code.get('text', '')} × {e['qty']:g},扣 {scoring.entry_points(e):g} 分 {note}")

    lines += ["", "## 優點與亮點"]
    highlights = []
    for it in rubric.items():
        if it["id"] in ("六", "八"):
            continue
        if res["deducted"][it["id"]] == 0 and it["points"] > 0:
            highlights.append(f"{it['id']}、{it['name']}:全數達標,無缺失。")
    if u["mgmt_text"] and scoring.mgmt_bonus(u) > 0:
        highlights.append(f"一-3、進退管理機制:業務科核給 {scoring.mgmt_bonus(u):g} 分。說明:{u['mgmt_text']}")
    funding_cases = [c for c in db.get_funding_cases(unit) if c["confirmed"]]
    if funding_cases:
        total = sum(c["amount"] for c in funding_cases)
        highlights.append(f"六、全年度爭取經費:已確認 {len(funding_cases)} 筆,共 {total:,} 元,得 {res['scores']['六']:g} 分。")
    if u["h2_text"] and not u["h2_rejected"]:
        highlights.append(f"八-2、救護技能競賽:{u['h2_text']}。")
    for c in db.get_creative_cases(unit):
        if c["confirmed"]:
            highlights.append(f"八-3、建設性作為:{c['description']}。")
    lines += [f"- {h}" for h in highlights] if highlights else ["(本次複評尚無特別亮點紀錄)"]
    return "\n".join(lines)


def render(user: dict):
    st.title("分隊重點優缺失表")
    st.caption("彙整每個分隊的得分、扣分缺失與亮點,方便列印或存檔。業務科複評完成後產出的內容才是正式結果。")
    battalion = None if user["role"] == "hq" else user["battalion"]
    units = db.list_units(battalion)
    if not units:
        st.info("尚無分隊資料。")
        return
    names = [u["name"] for u in units]
    label = (lambda n: f"{n}({db.get_unit(n)['battalion']})") if user["role"] == "hq" else (lambda n: n)
    unit = st.selectbox("選擇分隊", names, format_func=label)

    md = _unit_report_markdown(unit)
    st.markdown(md)
    st.download_button("下載這份重點優缺失表", md, file_name=f"{unit}_評核重點優缺失表.md", mime="text/markdown")

    st.divider()
    all_md = "\n\n---\n\n".join(_unit_report_markdown(u["name"]) for u in units)
    st.download_button("下載全部分隊彙整檔", all_md, file_name="分隊評核重點優缺失表_彙整.md", mime="text/markdown")
