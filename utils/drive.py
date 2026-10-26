"""Google Drive 串接:找出每個分隊、每個評核項次對應的 Drive 資料夾,提供連結與唯讀檔案清單。

系統不經手檔案內容(服務帳戶沒有儲存配額,無法在個人 Google 帳號底下建立有內容的檔案),
分隊直接在 Drive 資料夾裡上傳與管理,本系統只負責找到正確的資料夾並顯示連結。

資料夾結構(沿用現有):
  縣局根資料夾 / 大隊 / 115年度義勇消防組織評核資料(分隊名稱) / 01_編組狀況 ...
資料夾以名稱比對,不需要維護 ID 對照表。啟用方式見 README「串接 Google Drive」。
"""
import json

import streamlit as st

from utils import db

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"

# 評核項次 → 資料夾名稱關鍵字(依序比對,第一個符合的即採用)與新建資料夾時的名稱
ITEM_FOLDERS = {
    "一": (["編組"], "01_編組狀況"),
    "二": (["協勤民力資訊"], "02_協勤民力資訊系統建置"),
    "三": (["訓練"], "03_專業與常年訓練"),
    "四": (["協勤情形"], "04_協勤情形"),
    "五": (["裝備器材"], "05_裝備器材操作維護"),
    "六": (["爭取經費"], "06_全年度爭取經費"),
    "七": (["監督管理"], "07_監督管理情形"),
    "八": (["重大工作", "配合本局"], "08_配合本局年度重大工作"),
}


def _secrets() -> tuple[dict | None, str | None]:
    try:
        info = st.secrets.get("GOOGLE_SERVICE_ACCOUNT")
        root = st.secrets.get("DRIVE_ROOT_FOLDER_ID")
    except Exception:
        return None, None
    if not info or not root:
        return None, None
    return (json.loads(info) if isinstance(info, str) else dict(info)), str(root)


def enabled() -> bool:
    return _secrets()[0] is not None


@st.cache_resource
def _service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    info, _ = _secrets()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _children(parent_id: str, folders_only: bool = True) -> list[dict]:
    q = f"'{parent_id}' in parents and trashed=false"
    if folders_only:
        q += f" and mimeType='{FOLDER_MIME}'"
    out, token = [], None
    while True:
        r = _service().files().list(q=q, fields="nextPageToken, files(id,name,mimeType,webViewLink,size,createdTime)",
                                    pageSize=200, pageToken=token, supportsAllDrives=True,
                                    includeItemsFromAllDrives=True).execute()
        out += r.get("files", [])
        token = r.get("nextPageToken")
        if not token:
            return out


def pick_item_folder(item_id: str, names_ids: list[tuple[str, str]]) -> str | None:
    """從分隊資料夾底下的子資料夾名稱,找出對應評核項次的資料夾 ID。"""
    keywords, _ = ITEM_FOLDERS[item_id]
    for kw in keywords:
        for name, fid in names_ids:
            if kw in name:
                return fid
    return None


def find_unit_folder(unit: str, battalion: str) -> str | None:
    _, root = _secrets()
    # Drive 資料夾名稱有時與系統分隊名稱不同(例如資料夾叫「海端分隊」),依序嘗試各種寫法
    candidates = [unit, unit.replace("義消分隊", "分隊")]
    for b in _children(root):
        if battalion.replace("大隊", "") in b["name"]:
            folders = _children(b["id"])
            for name in candidates:
                for u in folders:
                    if name in u["name"]:
                        return u["id"]
            # 最後手段:資料夾名稱有錯字時,用分隊核心名稱(例如「長濱」)比對,且必須只有一個符合
            core = unit
            for suffix in ("救災義消分隊", "救護義消分隊", "義消分隊"):
                core = core.replace(suffix, "")
            hits = [u for u in folders if core and core in u["name"]]
            if len(hits) == 1:
                return hits[0]["id"]
    return None


def item_folder_id(unit: str, battalion: str, item_id: str, create: bool = False) -> str | None:
    """取得(必要時建立)分隊某評核項次的資料夾 ID,結果快取在資料庫。"""
    with db.get_conn() as c:
        row = c.execute("SELECT folder_id FROM drive_map WHERE unit=? AND item=?", (unit, item_id)).fetchone()
        if row:
            return row["folder_id"]
    unit_folder = find_unit_folder(unit, battalion)
    if not unit_folder:
        return None
    subs = [(f["name"], f["id"]) for f in _children(unit_folder)]
    fid = pick_item_folder(item_id, subs)
    if not fid and create:
        fid = _service().files().create(
            body={"name": ITEM_FOLDERS[item_id][1], "mimeType": FOLDER_MIME, "parents": [unit_folder]},
            fields="id", supportsAllDrives=True).execute()["id"]
    if fid:
        with db.get_conn() as c:
            c.execute("INSERT OR REPLACE INTO drive_map(unit,item,folder_id) VALUES (?,?,?)", (unit, item_id, fid))
    return fid


def subfolder_id(unit: str, battalion: str, item_id: str, sub_key: str, sub_name: str,
                 keywords: list[str], create: bool = False) -> str | None:
    """某分隊某項次資料夾底下的子資料夾 ID(必要時建立),結果快取在資料庫(key 為「項次:子資料夾」)。
    用於評核項目需要再分層的情形,例如第三項的「專業訓練」「常年訓練」。"""
    cache_key = f"{item_id}:{sub_key}"
    with db.get_conn() as c:
        row = c.execute("SELECT folder_id FROM drive_map WHERE unit=? AND item=?", (unit, cache_key)).fetchone()
        if row:
            return row["folder_id"]
    parent = item_folder_id(unit, battalion, item_id, create=create)
    if not parent:
        return None
    subs = [(f["name"], f["id"]) for f in _children(parent)]
    fid = None
    for kw in keywords:
        fid = next((sid for name, sid in subs if kw in name), None)
        if fid:
            break
    if not fid and create:
        fid = _service().files().create(
            body={"name": sub_name, "mimeType": FOLDER_MIME, "parents": [parent]},
            fields="id", supportsAllDrives=True).execute()["id"]
    if fid:
        with db.get_conn() as c:
            c.execute("INSERT OR REPLACE INTO drive_map(unit,item,folder_id) VALUES (?,?,?)", (unit, cache_key, fid))
    return fid


def folder_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


@st.cache_data(ttl=60, show_spinner=False)
def list_files(folder_id: str) -> list[dict]:
    """列出資料夾內的檔案(不含子資料夾)。有 60 秒快取,避免每次畫面重整都呼叫 Drive API。
    系統不經手檔案內容,只用來顯示資料夾裡目前有什麼,實際上傳請在 Drive 裡直接操作。"""
    return [f for f in _children(folder_id, folders_only=False) if f.get("mimeType") != FOLDER_MIME]
