"""義消專長資料庫「系統帳號備份」的密碼雜湊方式。

那個系統的雜湊演算法沒有文件,這裡列出常見做法的候選清單;用 tools/detect_hash.py 以真實帳號測出
符合哪一種,再把名稱填進 secrets 的 ACCOUNT_HASH_SCHEME。
"""
import hashlib
import hmac

PBKDF2_ITERATIONS = [1_000, 10_000, 50_000, 100_000, 120_000, 150_000, 200_000, 260_000,
                     310_000, 390_000, 480_000, 600_000]


def _schemes() -> dict:
    s = {}
    for salt_kind in ("text", "bytes"):
        def salt_of(salt, kind=salt_kind):
            return salt.encode() if kind == "text" else bytes.fromhex(salt)
        s[f"sha256_salt_pw_{salt_kind}"] = lambda pw, salt, f=salt_of: hashlib.sha256(f(salt) + pw.encode()).hexdigest()
        s[f"sha256_pw_salt_{salt_kind}"] = lambda pw, salt, f=salt_of: hashlib.sha256(pw.encode() + f(salt)).hexdigest()
        s[f"hmac_sha256_key_salt_{salt_kind}"] = lambda pw, salt, f=salt_of: hmac.new(f(salt), pw.encode(), hashlib.sha256).hexdigest()
        s[f"hmac_sha256_key_pw_{salt_kind}"] = lambda pw, salt, f=salt_of: hmac.new(pw.encode(), f(salt), hashlib.sha256).hexdigest()
        for n in PBKDF2_ITERATIONS:
            s[f"pbkdf2_sha256_{n}_{salt_kind}"] = (
                lambda pw, salt, f=salt_of, n=n: hashlib.pbkdf2_hmac("sha256", pw.encode(), f(salt), n).hex())
    return s


SCHEMES = _schemes()
DEFAULT_SCHEME = "pbkdf2_sha256_260000_bytes"  # 義消專長資料庫實測結果(2026-10-25,以 admin 帳號比對)


def hash_password(password: str, salt: str, scheme: str | None = None) -> str:
    return SCHEMES[scheme or DEFAULT_SCHEME](password, salt)


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.strip().lower().encode())


def verify(password: str, salt: str, expected_hash: str, scheme: str | None = None) -> bool:
    try:
        return _same(hash_password(password, salt, scheme), expected_hash)
    except ValueError:  # 鹽值不是十六進位字串,視為驗證失敗
        return False


def detect(password: str, salt: str, expected_hash: str) -> list[str]:
    """回傳所有能從密碼+鹽值算出 expected_hash 的候選做法名稱。"""
    return [name for name, fn in SCHEMES.items() if _same(fn(password, salt), expected_hash)]
