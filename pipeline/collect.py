"""1단계: PubMed에서 저널별 최근 논문 N편의 투고·승인·게재일을 수집 (증분).

실행:  python -m pipeline.collect
- 이전 실행에서 이미 받은 PMID는 다시 받지 않습니다 (캐시 재사용).
- 각 저널의 '현재 최근 N편'에 들지 않게 된 옛 논문은 캐시에서 빠집니다.
"""
import datetime as dt
import sys
import time

import pandas as pd

from . import config as C
from .journals import load_journals
from .ncbi import NCBIClient
from .parse import parse_pubmed_xml

DATE_COLS = ["received", "revised", "accepted", "epub"]


def build_term(row):
    keys = [f'"{x}"[is]' for x in (row["issn"], row["eissn"]) if isinstance(x, str) and x]
    if keys:
        base = "(" + " OR ".join(keys) + ")"
    else:
        base = f'"{row["title"]}"[ta]'
    excl = " OR ".join(f'"{p}"[pt]' for p in C.EXCLUDE_PUBTYPES)
    return f"{base} NOT ({excl})"


def load_cache():
    if C.ARTICLES_CACHE.exists():
        return pd.read_csv(C.ARTICLES_CACHE, dtype=str)
    return pd.DataFrame(columns=["jid", "pmid", *DATE_COLS, "issn_print", "issn_electronic",
                                 "journal_title", "iso_abbrev", "pubtypes"])


def run(client=None, journals=None, today=None, log=print):
    client = client or NCBIClient(C.NCBI_API_KEY, C.NCBI_EMAIL, C.NCBI_TOOL)
    journals = journals if journals is not None else load_journals(C.INPUT_JOURNALS)
    if C.LIMIT_JOURNALS:
        journals = journals.head(C.LIMIT_JOURNALS)
    today = today or dt.date.today()
    mindate = (today - dt.timedelta(days=C.LOOKBACK_DAYS)).strftime("%Y/%m/%d")
    maxdate = today.strftime("%Y/%m/%d")

    cache = load_cache()
    known = set(cache["pmid"])
    log(f"저널 {len(journals):,}개 | 캐시 논문 {len(known):,}편 | API키 {'있음' if client.api_key else '없음'}")

    # ① 저널별 최근 N편 PMID 조회
    current = {}       # pmid -> jid
    status = []
    t0 = time.time()
    for i, row in journals.iterrows():
        try:
            ids, count = client.esearch_pmids(build_term(row), mindate, maxdate, C.MAX_PER_JOURNAL)
            err = ""
        except Exception as e:  # 한 저널 실패가 전체를 멈추지 않도록
            ids, count, err = [], 0, str(e)[:200]
        for p in ids:
            current.setdefault(p, row["jid"])
        status.append({"jid": row["jid"], "found_in_window": count, "sampled": len(ids), "error": err})
        if (i + 1) % 200 == 0:
            log(f"  검색 {i + 1:,}/{len(journals):,} ({time.time() - t0:.0f}초)")

    # ② 새 PMID만 상세 조회
    new_ids = [p for p in current if p not in known]
    log(f"현재 표본 {len(current):,}편 중 신규 {len(new_ids):,}편 상세 조회")
    fetched = []
    for b in range(0, len(new_ids), C.EFETCH_BATCH):
        batch = new_ids[b:b + C.EFETCH_BATCH]
        try:
            rows = parse_pubmed_xml(client.efetch_pubmed_xml(batch))
        except Exception as e:
            log(f"  efetch 실패 ({b}~): {e}")
            continue
        for r in rows:
            r["jid"] = current.get(r["pmid"])
        fetched.extend(rows)
        if (b // C.EFETCH_BATCH + 1) % 20 == 0:
            log(f"  상세 {b + len(batch):,}/{len(new_ids):,}")

    new_df = pd.DataFrame(fetched)
    if not new_df.empty:
        for c in DATE_COLS:
            new_df[c] = new_df[c].map(lambda d: d.isoformat() if d else None)

    # ③ 병합 + 현재 표본에 없는 옛 논문 제거
    merged = pd.concat([cache, new_df], ignore_index=True)
    merged = merged[merged["pmid"].isin(current.keys())].drop_duplicates("pmid", keep="last")
    merged["jid"] = merged["pmid"].map(current)

    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(C.ARTICLES_CACHE, index=False, compression="gzip")
    st = pd.DataFrame(status)
    st["checked_at"] = today.isoformat()
    st.to_csv(C.STATUS_CACHE, index=False)
    n_err = (st["error"] != "").sum()
    log(f"완료: 논문 {len(merged):,}편 저장, 검색 오류 저널 {n_err}개")
    return merged, st


if __name__ == "__main__":
    if not C.INPUT_JOURNALS.exists():
        sys.exit(f"입력 파일이 없습니다: {C.INPUT_JOURNALS}")
    run()
