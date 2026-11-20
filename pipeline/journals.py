"""입력 CSV(저널 목록·APC 목록) 읽기. 컬럼명은 자동 인식합니다.

인식 규칙 (대소문자 무시):
  저널명  : 'title' 또는 'journal' 또는 '저널' 이 들어간 컬럼
  ISSN    : 'eissn' / 'e-issn' / 'electronic' / '온라인' 이 들어가면 eISSN,
            그 외 'issn' 이 들어가면 print ISSN
  출판사  : 'publisher' 또는 '출판사' 또는 '컨소시엄'
CSV/엑셀 모두 가능 (.csv, .xlsx).
"""
import re

import pandas as pd

from .parse import normalize_issn


def _read_any(path):
    if str(path).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, dtype=str)
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없습니다: {path}")


def _detect(cols):
    title = issn = eissn = pub = None
    for c in cols:
        k = re.sub(r"[\s_\-]", "", str(c).lower())
        if eissn is None and ("eissn" in k or "electronic" in k or "온라인" in k):
            eissn = c
        elif issn is None and "issn" in k:
            issn = c
        elif title is None and ("title" in k or "journal" in k or "저널" in k or "학술지" in k):
            title = c
        elif pub is None and ("publisher" in k or "출판사" in k or "컨소시엄" in k):
            pub = c
    if title is None and issn is None:
        raise ValueError(f"저널명/ISSN 컬럼을 찾지 못했습니다. 현재 컬럼: {list(cols)}")
    return title, issn, eissn, pub


def norm_title(t):
    """저널명 '완전 일치' 비교용: 대소문자·앞뒤공백·연속공백만 정리 (유사어 추정 없음)."""
    if not isinstance(t, str):
        return ""
    return re.sub(r"\s+", " ", t).strip().casefold()


def load_table(path):
    df = _read_any(path)
    title, issn, eissn, pub = _detect(df.columns)
    out = pd.DataFrame({
        "title": df[title].fillna("").str.strip() if title else "",
        "issn": df[issn].map(normalize_issn) if issn else None,
        "eissn": df[eissn].map(normalize_issn) if eissn else None,
        "publisher": df[pub].fillna("").str.strip() if pub else "",
    })
    # ISSN 칸 하나에 "1234-5678 / 2345-6789" 처럼 두 개가 들어있는 경우 분리
    if issn:
        both = df[issn].fillna("").map(lambda s: re.findall(r"\d{4}-?\d{3}[\dXx]", s))
        out.loc[both.map(len) >= 2, "eissn"] = out["eissn"].where(
            out["eissn"].notna(), both.map(lambda l: normalize_issn(l[1]) if len(l) >= 2 else None))
        out["issn"] = out["issn"].where(out["issn"].notna(), both.map(lambda l: normalize_issn(l[0]) if l else None))
    return out


def load_journals(path):
    df = load_table(path)
    df["jid"] = df["issn"].fillna(df["eissn"])
    # ISSN이 둘 다 없으면 저널명으로 키 생성
    no_id = df["jid"].isna()
    df.loc[no_id, "jid"] = "T:" + df.loc[no_id, "title"].map(norm_title)
    df = df[df["jid"] != "T:"].drop_duplicates("jid").reset_index(drop=True)
    return df
