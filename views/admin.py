"""帳號管理(業務科)與修改自己的密碼(所有角色)。"""
import io

import pandas as pd
import streamlit as st

from utils import auth, cloud_accounts, db


def _accounts() -> list[dict]:
    with db.get_conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT account, role, unit, battalion FROM accounts ORDER BY role, account")]


def render_admin(user: dict):
    st.title("帳號管理")
    if cloud_accounts.enabled():
        st.info("登入帳號與密碼和「義消專長資料庫」共用(讀取雲端試算表「系統帳號備份」,約 1 分鐘同步)。"
                "新增帳號、改密碼、停用請在專長資料庫操作。這裡只顯示目前的對應狀況。")
        accounts = cloud_accounts.fetch_accounts()
        rows = []
        for a in accounts.values():
            u, msg = cloud_accounts.to_user(a)
            rows.append({"帳號": a["account"], "所屬單位": a["org"], "狀態": a["status"],
                         "本系統角色": auth.ROLE_LABEL[u["role"]] if u else
                         ("不評核" if msg == "此單位不在本次評核範圍" else "未對應"),
                         "對應分隊": "、".join(u["units"]) if u and u["units"] else (u["battalion"] if u and u["battalion"] else "")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("名稱對照表在 data/unit_alias.json。顯示「未對應」的帳號無法登入本系統。")
        return
    st.caption("初始密碼只會顯示一次,請當場抄下或下載後交給對方,並請對方登入後自行改密碼。")

    st.subheader("新增分隊")
    c1, c2 = st.columns(2)
    battalion = c1.text_input("所屬大隊(例如:臺東大隊)").strip()
    unit = c2.text_input("分隊名稱").strip()
    if st.button("新增分隊並建立帳號", disabled=not (battalion and unit)):
        if db.get_unit(unit) or any(a["account"] == unit for a in _accounts()):
            st.error("已有同名分隊或帳號")
        else:
            pw = auth.create_unit_account(unit, battalion)
            if not any(a["account"] == battalion for a in _accounts()):
                bpw = auth.gen_password()
                auth.set_account(battalion, bpw, "battalion", battalion=battalion)
                st.warning(f"同時建立大隊帳號「{battalion}」,初始密碼:{bpw}")
            st.success(f"帳號:{unit}  初始密碼:{pw}")

    st.subheader("批次匯入分隊")
    st.caption("CSV 需有兩欄:大隊、分隊。匯入後可下載含初始密碼的名單。")
    up = st.file_uploader("上傳 CSV", type=["csv"], key="bulk")
    if up and st.button("匯入"):
        df = pd.read_csv(up, dtype=str).fillna("")
        if not {"大隊", "分隊"} <= set(df.columns):
            st.error("找不到「大隊」「分隊」欄位")
        else:
            out = []
            existing = {a["account"] for a in _accounts()}
            for _, r in df.iterrows():
                b, u = r["大隊"].strip(), r["分隊"].strip()
                if not b or not u or u in existing:
                    continue
                out.append({"帳號": u, "角色": "分隊", "初始密碼": auth.create_unit_account(u, b)})
                existing.add(u)
                if b not in existing:
                    bpw = auth.gen_password()
                    auth.set_account(b, bpw, "battalion", battalion=b)
                    existing.add(b)
                    out.append({"帳號": b, "角色": "大隊", "初始密碼": bpw})
            if out:
                buf = io.BytesIO()
                pd.DataFrame(out).to_csv(buf, index=False, encoding="utf-8-sig")
                st.success(f"已建立 {len(out)} 個帳號")
                st.download_button("下載初始密碼名單", buf.getvalue(), "initial_accounts.csv", "text/csv")
            else:
                st.info("沒有需要新增的分隊")

    st.subheader("帳號清單與重設密碼")
    accounts = _accounts()
    st.dataframe(pd.DataFrame([{"帳號": a["account"], "角色": auth.ROLE_LABEL[a["role"]],
                                "大隊": a["battalion"] or "", "分隊": a["unit"] or ""} for a in accounts]),
                 hide_index=True, width="stretch")
    target = st.selectbox("選擇帳號", [a["account"] for a in accounts])
    if st.button("重設密碼"):
        st.success(f"{target} 的新密碼:{auth.reset_password(target)}")


def render_password(user: dict):
    st.title("修改密碼")
    if cloud_accounts.enabled():
        st.info("密碼與「義消專長資料庫」共用,請在專長資料庫修改,這裡約 1 分鐘後同步。")
        return
    st.write(f"目前帳號:**{user['account']}**({auth.ROLE_LABEL[user['role']]})")
    old = st.text_input("目前密碼", type="password")
    new = st.text_input("新密碼(至少 8 碼)", type="password")
    new2 = st.text_input("再輸入一次新密碼", type="password")
    if st.button("修改", type="primary"):
        ok, _ = auth.verify(user["account"], old)
        if not ok:
            st.error("目前密碼錯誤")
        elif len(new) < 8:
            st.error("新密碼至少 8 碼")
        elif new != new2:
            st.error("兩次輸入的新密碼不一致")
        else:
            auth.change_password(user["account"], new)
            st.success("已修改")
