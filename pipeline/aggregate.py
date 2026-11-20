
"""2단계: 논문 단위 캐시 → 저널별 통계(중앙값·사분위) + APC 매칭 → 웹용 JSON/CSV.
 
실행:  python -m pipeline.aggregate
"""
import datetime as dt
import json
 
import numpy as np
import pandas as pd
 
from . import config as C
from .journals import load_journals, load_table, norm_title
 
KST = dt.timezone(dt.timedelta(hours=9))
 
 
def _days(a, b):
    a, b = pd.to_datetime(a, errors="coerce"), pd.to_datetime(b, errors="coerce")
    return (b - a).dt.days
 
 
def _stats(s):
    s = s.dropna()
    s = s[(s >= C.MIN_VALID_DAYS) & (s <= C.MAX_VALID_DAYS)]
    if s.empty:
        return None
    q1, med, q3 = np.percentile(s, [25, 50, 75])
    return {"n": int(len(s)), "median": round(float(med)), "q1": round(float(q1)),
            "q3": round(float(q3)), "min": int(s.min()), "max": int(s.max()),
            "short": int((s < C.SHORT_DAYS).sum())}
 
 
def _s(v):
    """NaN/None → '' (JSON에 NaN이 들어가면 브라우저가 파일을 못 읽음)"""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v)
 
 
def reliability(n):
    for th, label in C.RELIABILITY:
        if n >= th:
            return label
    return "없음"
 
 
def build_apc_matcher(apc):
    issns = set(apc["issn"].dropna()) | set(apc["eissn"].dropna())
    titles = {norm_title(t) for t in apc["title"] if norm_title(t)}
    pub_by_issn = {}
    for _, r in apc.iterrows():
        for k in (r["issn"], r["eissn"]):
            if isinstance(k, str):
                pub_by_issn[k] = r["publisher"]
 
    def match(issn_list, title_list):
        """완전 일치만 인정. ISSN 우선, 다음 정확한 저널명. 출판사·유사명 추정 없음."""
        for i in issn_list:
            if i and i in issns:
                return "ISSN", pub_by_issn.get(i, "")
        for t in title_list:
            if norm_title(t) and norm_title(t) in titles:
                return "TITLE", ""
        return "", ""
    return match
 
 
def run(journals=None, apc=None, articles=None, status=None, now=None):
    journals = journals if journals is not None else load_journals(C.INPUT_JOURNALS)
    apc = apc if apc is not None else (load_table(C.INPUT_APC) if C.INPUT_APC.exists()
                                       else pd.DataFrame(columns=["title", "issn", "eissn", "publisher"]))
    articles = articles if articles is not None else pd.read_csv(C.ARTICLES_CACHE, dtype=str)
    status = status if status is not None else (pd.read_csv(C.STATUS_CACHE, dtype=str).fillna("")
                                                if C.STATUS_CACHE.exists() else pd.DataFrame(columns=["jid"]))
    now = now or dt.datetime.now(KST)
 
    articles = articles.copy()
    articles["d_rec_acc"] = _days(articles["received"], articles["accepted"])
    articles["d_acc_pub"] = _days(articles["accepted"], articles["epub"])
    groups = dict(tuple(articles.groupby("jid")))
    st_map = status.set_index("jid").to_dict("index") if len(status) else {}
    match_apc = build_apc_matcher(apc)
 
    out = []
    for _, j in journals.iterrows():
        g = groups.get(j["jid"], pd.DataFrame())
        ra = _stats(g["d_rec_acc"]) if len(g) else None
        ap = _stats(g["d_acc_pub"]) if len(g) else None
        title = _s(j["title"]) or (g["journal_title"].dropna().iloc[0] if len(g) and g["journal_title"].notna().any() else "")
        abbrev = g["iso_abbrev"].dropna().iloc[0] if len(g) and g["iso_abbrev"].notna().any() else ""
        issns = [j["issn"], j["eissn"]]
        if len(g):  # PubMed 레코드에 있는 ISSN도 APC 대조에 사용
            issns += list(g["issn_print"].dropna().unique()) + list(g["issn_electronic"].dropna().unique())
        apc_by, apc_pub = match_apc([i for i in issns if isinstance(i, str) and i], [title])
        st = st_map.get(j["jid"], {})
        out.append({
            "title": title,
            "abbrev": abbrev,
            "issn": _s(j["issn"]),
            "eissn": _s(j["eissn"]),
            "publisher": _s(j["publisher"]) or _s(apc_pub),
            "n_sampled": int(len(g)),
            "n_found": int(st.get("found_in_window") or 0),
            "rec_acc": ra,
            "acc_pub": ap,
            "reliability": reliability(ra["n"] if ra else 0),
            "latest_accepted": _s(g["accepted"].dropna().max() if len(g) and g["accepted"].notna().any() else ""),
            "apc": bool(apc_by),
            "apc_match": apc_by,
            "error": _s(st.get("error")),
        })
 
    meta = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M KST"),
        "lookback_days": C.LOOKBACK_DAYS,
        "max_per_journal": C.MAX_PER_JOURNAL,
        "valid_days": [C.MIN_VALID_DAYS, C.MAX_VALID_DAYS],
        "n_journals": len(out),
        "n_with_stats": sum(1 for o in out if o["rec_acc"]),
        "n_articles": int(len(articles)),
        "n_apc_list": int(len(apc)),
        "n_apc_matched": sum(1 for o in out if o["apc"]),
    }
    C.OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(C.OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "journals": out}, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
 
    # 엑셀에서 바로 열 수 있는 다운로드용 CSV
    flat = pd.DataFrame([{
        "저널명": o["title"], "약어": o["abbrev"], "ISSN": o["issn"], "eISSN": o["eissn"],
        "출판사": o["publisher"],
        "투고→승인 중앙값(일)": o["rec_acc"]["median"] if o["rec_acc"] else None,
        "투고→승인 Q1": o["rec_acc"]["q1"] if o["rec_acc"] else None,
        "투고→승인 Q3": o["rec_acc"]["q3"] if o["rec_acc"] else None,
        "산출 논문 수": o["rec_acc"]["n"] if o["rec_acc"] else 0,
        "승인→온라인게재 중앙값(일)": o["acc_pub"]["median"] if o["acc_pub"] else None,
        "신뢰도": o["reliability"], "최근 승인일": o["latest_accepted"],
        "전남대 APC 지원": "지원 목록 일치" if o["apc"] else "목록에서 확인되지 않음",
    } for o in out])
    flat.to_csv(C.OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"저장: {C.OUTPUT_JSON.name} (저널 {meta['n_journals']:,}개, 통계 산출 {meta['n_with_stats']:,}개, "
          f"APC 일치 {meta['n_apc_matched']}개)")
    return meta, out
 
 
if __name__ == "__main__":
    run()
 
