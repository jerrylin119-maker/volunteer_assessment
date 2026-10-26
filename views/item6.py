"""第六項「全年度爭取經費情形」(2 分)。分隊逐筆填寫案件說明與金額,系統自動加總並依門檻換算分數;
業務科逐筆確認後才計入正式金額(未確認的案件分隊可自行刪除)。"""
import streamlit as st

from utils import db, rubric, scoring

ITEM = "六"


def _tier_text() -> str:
    tiers = rubric.load()["funding_tiers"]
    return "、".join(f"{t:,} 元以上得 {p:g} 分" for t, p in tiers)


def unit_panel(unit: str, who: str, locked: bool):
    """分隊填報畫面:逐筆新增案件與金額,系統自動加總並顯示換算後的分數(自評試算)。"""
    st.markdown("##### 爭取經費案件登錄")
    st.caption("爭取本局以外經費補助(民意代表、各級機關核定或外界捐贈),請逐筆填寫案件說明與金額。"
               f"整年度累計金額對照:{_tier_text()}。相關佐證資料請上傳到上方的雲端資料夾,業務科會逐筆確認。")
    rows = db.get_funding_cases(unit)
    for r in rows:
        c1, c2, c3 = st.columns([4, 2, 1])
        c1.write(("✅ " if r["confirmed"] else "⏳ ") + r["description"])
        c2.write(f"{r['amount']:,} 元")
        if not locked and not r["confirmed"] and c3.button("刪除", key=f"delfund_{r['id']}"):
            db.delete_funding_case(r["id"])
            st.rerun()
    c1, c2, c3 = st.columns([4, 2, 1])
    desc = c1.text_input("案件說明", key=f"newfund_desc_{unit}", disabled=locked, label_visibility="collapsed",
                         placeholder="例如:○○議員設備補助")
    amount = c2.number_input("金額(元)", min_value=0, step=10000, key=f"newfund_amt_{unit}", disabled=locked,
                             label_visibility="collapsed")
    if c3.button("新增", key=f"addfund_{unit}", disabled=locked or not desc.strip() or amount <= 0):
        db.add_funding_case(unit, desc.strip(), int(amount), who)
        st.success("已新增")
        st.rerun()

    confirmed_total = sum(r["amount"] for r in rows if r["confirmed"])
    all_total = sum(r["amount"] for r in rows)
    st.divider()
    st.metric("業務科已確認金額", f"{confirmed_total:,} 元")
    st.caption(f"已確認換算:{scoring.funding_points(confirmed_total):g} / 2 分。"
               f"分隊目前填寫總額 {all_total:,} 元(含業務科尚未確認的部分,僅供參考)。")


def review_panel(unit: str, user: dict):
    """業務科(逐筆確認)與大隊(唯讀)的複評畫面。"""
    is_hq = user["role"] == "hq"
    st.markdown("##### 爭取經費案件(業務科逐筆確認)")
    rows = db.get_funding_cases(unit)
    if not rows:
        st.caption("分隊尚未填寫任何案件。")
    for r in rows:
        c1, c2, c3 = st.columns([4, 2, 2])
        c1.write(r["description"])
        c2.write(f"{r['amount']:,} 元")
        if is_hq:
            new_val = c3.checkbox("確認計入", value=bool(r["confirmed"]), key=f"fundconfirm_{r['id']}")
            if new_val != bool(r["confirmed"]):
                db.set_funding_case_confirmed(r["id"], new_val)
                st.rerun()
        else:
            c3.write("已確認" if r["confirmed"] else "未確認")
    total = sum(r["amount"] for r in rows if r["confirmed"])
    pts = scoring.funding_points(total)
    st.divider()
    st.metric("已確認總金額", f"{total:,} 元")
    st.caption(f"依門檻換算:{pts:g} / 2 分(" + _tier_text() + ")。")
    if not is_hq:
        st.caption("這一項由業務科確認,大隊僅供檢視。")
