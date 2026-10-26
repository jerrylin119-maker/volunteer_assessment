"""依評核表計分:分隊總分、大隊總分。"""
from utils import db, roster, rubric


def entry_points(entry: dict) -> float:
    c = rubric.code(entry["code"])
    if not c:
        return 0.0
    pts = entry["qty"] * c["unit_score"]
    return min(pts, c["cap"]) if c["cap"] else pts


def funding_points(amount: int) -> float:
    for threshold, pts in rubric.load()["funding_tiers"]:
        if amount >= threshold:
            return pts
    return 0.0


def funding_amount(unit: str, source: str) -> int:
    """第六項:分隊逐筆填寫的爭取經費案件加總。'review' 只算業務科已確認的案件(正式金額),
    'self' 把分隊自己填的案件全部加總(自評試算,僅供參考)。"""
    cases = db.get_funding_cases(unit)
    if source == "review":
        return sum(c["amount"] for c in cases if c["confirmed"])
    return sum(c["amount"] for c in cases)


def staffing_data(u: dict | None) -> dict:
    """編制、現有人數、平均年齡:優先用專長資料庫試算表的即時資料,讀不到時改用業務科手動登錄的數字。"""
    if not u:
        return {"authorized": 0, "headcount": 0, "avg_age": 0, "source": "manual"}
    auto = roster.stats(u["name"])
    if auto:
        return {**u, **auto, "source": "sheet"}
    return {**u, "source": "manual"}


def staffing_bonus(u: dict | None) -> float:
    """第一項 3-(1):編組達編制 90% 以上且平均年齡達標加分,由系統資料(編制、現有人數、平均年齡)自動計算。"""
    cfg = rubric.load()["item1"]
    if not u or not u.get("authorized") or not u.get("avg_age"):
        return 0.0
    if u["headcount"] / u["authorized"] < cfg["min_ratio"]:
        return 0.0
    for age_limit, pts in sorted(cfg["age_tiers"]):
        if u["avg_age"] <= age_limit:
            return float(pts)
    return 0.0


def mgmt_bonus(u: dict | None) -> float:
    """第一項 3-(2):進退管理機制,業務科依分隊說明與佐證評斷給分,最高 3 分。"""
    if not u or not u.get("mgmt_scored"):  # 業務科尚未評分時不計
        return 0.0
    return max(0.0, min(float(u.get("mgmt_score") or 0), rubric.load()["item1"]["mgmt_max"]))


def collect_entries(unit: str, source: str) -> list[dict]:
    """某分隊的評核登錄。由業務科核對的項目(who=hq)不論 source,分隊畫面也要看到目前累計。"""
    entries = db.get_entries(unit, source)
    if source != "review":
        entries += [e for e in db.get_entries(unit, "review")
                    if (rubric.code(e["code"]) or {}).get("who") == "hq"]
    return entries


def age_provisional_deduction(u: dict | None) -> float:
    """第一項第 1 點的系統試算扣分:專長資料庫核對出年齡不在規定範圍的人數 × 單位扣分。
    正式成績以業務科確認後登錄的人數為準,所以只用在分隊畫面的「目前試算」。"""
    rows = staffing_data(u).get("age_outside_rows") if u else None
    return len(rows) * rubric.code("A1")["unit_score"] if rows else 0.0


def duty_deduction(u: dict | None) -> float:
    """第四項:分隊勾選「已完整檢附」時系統直接不扣這 2 分(等同 D1 的分數);未勾選則系統自動扣 2 分。
    不需要業務科手動登錄,業務科只需另外用 D2 登錄個別缺失。"""
    if not u or not u.get("duty_declared"):
        return float(rubric.code("D1")["unit_score"])
    return 0.0


def equip_roster_deduction(u: dict | None) -> float:
    """第五項 1:分隊勾選「已完成造冊管理」時系統直接不扣這 5 分(等同 E1);未勾選則系統自動扣 5 分。
    不需要業務科手動登錄,業務科只需另外用 E2 登錄個別缺失。"""
    if not u or not u.get("equip_roster_declared"):
        return float(rubric.code("E1")["unit_score"])
    return 0.0


def equip_check_deduction(u: dict | None) -> float:
    """第五項 2:分隊勾選「已完成個人裝備年度檢查」時系統直接不扣這 5 分(等同 E3);未勾選則系統自動扣 5 分。
    不需要業務科手動登錄,業務科只需另外用 E4 登錄個別缺失。"""
    if not u or not u.get("equip_check_declared"):
        return float(rubric.code("E3")["unit_score"])
    return 0.0


def finance_deduction(u: dict | None) -> float:
    """第七項:分隊勾選「公佈資料齊全」時系統直接不扣這 3 分;未勾選則系統自動扣完 3 分。
    業務科仍可用 G1 登錄個別缺失。"""
    if not u or not u.get("finance_declared"):
        return 3.0
    return 0.0


def h2_bonus(u: dict | None) -> float:
    """第八項 2:分隊填寫救護技能競賽參賽項目後直接加 1 分,業務科審核後可取消(h2_rejected)。"""
    if not u or not u.get("h2_text") or u.get("h2_rejected"):
        return 0.0
    return float(rubric.code("H2")["unit_score"])


def h3_bonus(unit: str) -> float:
    """第八項 3:分隊填寫的建設性作為,業務科每確認一案加 2 分。"""
    cases = db.get_creative_cases(unit)
    return sum(rubric.code("H3")["unit_score"] for c in cases if c["confirmed"])


def _deduct(entries: list[dict], pred) -> float:
    return sum(entry_points(e) for e in entries if pred(e) and (rubric.code(e["code"]) or {}).get("mode") == "扣分")


# 小點自動扣分:程式判斷哪個小點含有這個代碼,就加上對應的自動扣分函式,不需要業務科手動登錄
AUTO_SUBPOINT_DEDUCTIONS = {"E1": equip_roster_deduction, "E3": equip_check_deduction}


def subpoint_rows(it: dict, entries: list[dict], u: dict | None, source: str) -> list[dict]:
    """各小點的目前狀況:扣分、得分(有配分才有得分)、登錄數量、是否為系統試算。"""
    rows = []
    for sp in it.get("subpoints") or []:
        mine = [e for e in entries if e["code"] in sp["codes"]]
        d, provisional = _deduct(entries, lambda e: e["code"] in sp["codes"]), False
        if "A1" in sp["codes"] and source != "review" and not any(e["code"] == "A1" for e in entries):
            d, provisional = age_provisional_deduction(u), True  # 業務科尚未確認前,先用系統核對的人數試算
        for code, fn in AUTO_SUBPOINT_DEDUCTIONS.items():
            if code in sp["codes"]:
                d += fn(u)
        rows.append({"name": sp["name"], "points": sp["points"], "deduct": d, "provisional": provisional,
                     "qty": sum(e["qty"] for e in mine),
                     "score": None if sp["points"] is None else max(0.0, sp["points"] - d)})
    return rows


def _item_score(it: dict, entries: list[dict], u: dict | None, source: str) -> tuple[float, float]:
    """回傳 (本項得分, 本項扣分)。有小點配分的項目(第一項)各小點分開計分,互不挪用。"""
    subs = it.get("subpoints") or []
    if subs and all(sp["points"] is not None for sp in subs):
        rows = subpoint_rows(it, entries, u, source)
        return sum(r["score"] for r in rows), sum(r["deduct"] for r in rows)
    d = _deduct(entries, lambda e: e["item"] == it["id"])
    if it["id"] == "四":
        d += duty_deduction(u)
    elif it["id"] == "七":
        d += finance_deduction(u)
    return max(0.0, it["points"] - d), d


def unit_result(unit: str, source: str) -> dict:
    """source='self' 為分隊畫面的目前試算(含業務科已登錄的核對結果),'review' 為複評(正式成績)。"""
    entries = collect_entries(unit, source)
    u = db.get_unit(unit)
    scores, deducted = {}, {}
    for it in rubric.items():
        if it["id"] in ("六", "八"):
            continue
        scores[it["id"]], deducted[it["id"]] = _item_score(it, entries, u, source)
    scores["六"] = funding_points(funding_amount(unit, source))
    entry_bonus = sum(entry_points(e) for e in entries
                      if (rubric.code(e["code"]) or {}).get("mode") == "加分")
    auto = staffing_bonus(staffing_data(u))
    mgmt = mgmt_bonus(u)
    h2 = h2_bonus(u)
    h3 = h3_bonus(unit)
    bonus = entry_bonus + auto + mgmt + h2 + h3
    return {"scores": scores, "deducted": deducted, "bonus": bonus,
            "bonus_parts": {"系統自動(編組人數)": auto, "進退管理機制": mgmt,
                           "複訓到訓(第八項1)": entry_bonus, "救護技能競賽(第八項2)": h2, "建設性作為(第八項3)": h3},
            "total": sum(scores.values()) + bonus}


def battalion_result(battalion: str) -> dict:
    cfg = rubric.load()
    done = [u for u in db.list_units(battalion) if u["review_done"]]
    totals = [unit_result(u["name"], "review")["total"] for u in done]
    avg = sum(totals) / len(totals) if totals else None
    hq = db.get_hq_scores(battalion)
    topic_scores = []
    for i in range(len(cfg["hq_topics"])):
        h = hq.get(i, {"total": 0, "ok": 0})
        topic_scores.append(h["ok"] / h["total"] * cfg["hq_item_max"] if h["total"] else 0.0)
    hq_total = sum(topic_scores)
    weighted = avg * cfg["battalion_weight"] if avg is not None else None
    return {"unit_count": len(db.list_units(battalion)), "done_count": len(done), "avg": avg,
            "weighted": weighted, "topic_scores": topic_scores, "hq_total": hq_total,
            "total": None if weighted is None else weighted + hq_total}
