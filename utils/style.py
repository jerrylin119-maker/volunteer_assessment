"""整體視覺風格:頂部系統標題與自訂 CSS。純畫面調整,不影響任何資料或計分邏輯。"""
import streamlit as st

PRIMARY = "#c0392b"
PRIMARY_DARK = "#922b21"
ACCENT = "#f39c12"

ROLE_BADGE = {"unit": ("🏠", "分隊帳號", "#2980b9"), "battalion": ("🏛️", "大隊帳號", "#8e44ad"),
             "hq": ("⭐", "業務科帳號", PRIMARY)}


def inject_css():
    st.markdown(f"""
    <style>
    .block-container {{ padding-top: 1.2rem; max-width: 1100px; }}

    .evaltop-banner {{
        background: linear-gradient(120deg, {PRIMARY} 0%, {PRIMARY_DARK} 100%);
        border-radius: 14px; padding: 1.1rem 1.6rem; margin-bottom: 1.3rem;
        color: #fff; box-shadow: 0 4px 14px rgba(192,57,43,0.25);
        display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .6rem;
    }}
    .evaltop-banner .t1 {{ font-size: 1.5rem; font-weight: 800; letter-spacing: .5px; }}
    .evaltop-banner .t2 {{ font-size: .85rem; opacity: .9; margin-top: .15rem; }}
    .evaltop-badge {{
        background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.35);
        border-radius: 999px; padding: .35rem .9rem; font-size: .85rem; font-weight: 600; white-space: nowrap;
    }}

    [data-testid="stMetric"] {{
        background: #ffffff; border: 1px solid #ece7e6; border-radius: 12px;
        padding: .9rem 1rem .6rem; box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }}
    [data-testid="stMetricLabel"] {{ font-weight: 600; opacity: .75; }}

    h4, h5 {{
        border-left: 5px solid {PRIMARY}; padding-left: .6rem; margin-top: 1.1rem !important;
    }}

    [data-testid="stExpander"] {{
        border: 1px solid #eadfdd; border-radius: 10px; overflow: hidden;
    }}
    [data-testid="stExpander"] summary {{ font-weight: 600; }}

    .stButton > button[kind="primary"], .stDownloadButton > button, .stLinkButton > a {{
        border-radius: 8px !important; font-weight: 600 !important;
    }}

    [data-testid="stSidebar"] {{ border-right: 1px solid #eee; }}
    .sidebar-brand {{ font-size: 1.05rem; font-weight: 800; color: {PRIMARY}; margin-bottom: .1rem; }}
    .sidebar-sub {{ font-size: .78rem; color: #888; margin-bottom: 1rem; }}

    [data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; }}
    </style>
    """, unsafe_allow_html=True)


def top_banner(user: dict | None = None, subtitle: str = ""):
    """每個頁面最上方的系統標題橫幅,讓使用者一眼看出這是義消評核系統。"""
    right = ""
    if user:
        icon, label, color = ROLE_BADGE.get(user["role"], ("👤", "", PRIMARY))
        right = f'<div class="evaltop-badge">{icon} {user["account"]} · {label}</div>'
    st.markdown(f"""
    <div class="evaltop-banner">
      <div>
        <div class="t1">🚒 義勇消防組織業務評核系統</div>
        <div class="t2">{subtitle or "臺東縣消防局義勇消防組織業務評核"}</div>
      </div>
      {right}
    </div>
    """, unsafe_allow_html=True)


def sidebar_brand():
    st.markdown('<div class="sidebar-brand">🚒 義消評核系統</div>'
               '<div class="sidebar-sub">臺東縣消防局</div>', unsafe_allow_html=True)
