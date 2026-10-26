"""找出義消專長資料庫的密碼雜湊方式。在自己的電腦執行,密碼只在本機比對,不會傳出去。

用法:
    .venv/bin/python tools/detect_hash.py
"""
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import hashing  # noqa: E402


def ask_hex(prompt: str, length: int, example_hint: str) -> str:
    """要求貼上固定長度的英數字(0-9、a-f),格式不對就說明原因並重問。"""
    while True:
        value = input(prompt).strip()
        if re.fullmatch(rf"[0-9a-fA-F]{{{length}}}", value):
            return value
        print(f"  格式不對:這裡要貼的是試算表儲存格裡那串 {length} 個字元的英文字母與數字,{example_hint}")
        print(f"  你貼的內容共 {len(value)} 個字元。請回試算表點那一格、複製,再貼上來。\n")


print("在試算表「系統帳號備份」分頁,挑一個你知道密碼的帳號(例如 admin),找到它那一列。\n")
hash_value = ask_hex("貼上該列「密碼雜湊」那一格的內容(64 個字元): ", 64, "看起來像 ec69794366bf…")
salt = ask_hex("貼上該列「密碼鹽值」那一格的內容(32 個字元): ", 32, "看起來像 e43f89266279…")
password = getpass.getpass("輸入該帳號的密碼(打字時畫面不會顯示,打完按 Enter): ")

matches = hashing.detect(password, salt, hash_value)
if matches:
    print("\n符合的做法:", ", ".join(matches))
    print(f'請把上面這一行回報給 Claude,或在 .streamlit/secrets.toml 加上:ACCOUNT_HASH_SCHEME = "{matches[0]}"')
else:
    print("\n沒有任何候選做法符合。可能原因:密碼打錯、貼到別列的雜湊或鹽值、或對方系統用了清單以外的雜湊方式。")
    print("請先確認密碼和同一列的資料再試一次;仍不符合就請提供專長資料庫驗證密碼的程式碼。")
