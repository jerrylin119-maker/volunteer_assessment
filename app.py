"""義勇消防組織業務評核系統:各分隊隨時上傳評核資料,大隊與業務科複評並彙整成績。"""
import streamlit as st

from utils import auth, db, style
from views import admin, battalion, results, review, submit, summary

st.set_page_config(page_title="義消評核系統", page_icon="🚒", layout="wide")
style.inject_css()

db.init_db()
auth.seed_if_empty()


def login():
    st.markdown("<div style='height:3vh'></div>", unsafe_allow_html=True)
    col = st.columns([1, 1.3, 1])[1]
    with col:
        with st.container(border=True):
            st.markdown("<div style='text-align:center;font-size:3rem'>🚒</div>"
                        "<h2 style='text-align:center;margin-top:.2rem'>義勇消防組織業務評核系統</h2>"
                        "<p style='text-align:center;color:#888;margin-top:-.5rem'>臺東縣消防局</p>",
                        unsafe_allow_html=True)
            st.caption("請使用核發給貴單位的帳號登入。分隊帳號只能看到與修改自己分隊的資料。")
            with st.form("login"):
                account = st.text_input("帳號")
                password = st.text_input("密碼", type="password")
                if st.form_submit_button("登入", type="primary", width="stretch"):
                    user, msg = auth.verify(account.strip(), password)
                    if user:
                        st.session_state["user"] = user
                        st.rerun()
                    st.error(msg)


user = st.session_state.get("user")
if not user:
    login()
    st.stop()

pages = []
if user["role"] == "unit":
    pages.append(st.Page(lambda: submit.render(user), title="資料填報", icon="📝", url_path="submit"))
else:
    # 大隊帳號登入後先看到第九項(大隊評核項目),再進行所屬分隊的評核登錄
    pages.append(st.Page(lambda: battalion.render(user), title="第九項 大隊評核", icon="🏛️", url_path="battalion"))
    pages.append(st.Page(lambda: review.render(user), title="分隊評核登錄", icon="🔎", url_path="review"))
    pages.append(st.Page(lambda: results.render(user), title="成績總表", icon="📊", url_path="results"))
    pages.append(st.Page(lambda: summary.render(user), title="分隊重點優缺失表", icon="📋", url_path="summary"))
if user["role"] == "hq":
    pages.append(st.Page(lambda: admin.render_admin(user), title="帳號管理", icon="👥", url_path="accounts"))
pages.append(st.Page(lambda: admin.render_password(user), title="修改密碼", icon="🔑", url_path="password"))

with st.sidebar:
    style.sidebar_brand()
    st.markdown(f"**{user['account']}**  \n{auth.ROLE_LABEL[user['role']]}帳號")
    if st.button("登出", width="stretch"):
        st.session_state.clear()
        st.rerun()

style.top_banner(user)
st.navigation(pages).run()
