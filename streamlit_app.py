"""(선택) Streamlit 버전 — 정적 웹과 같은 docs/data/journals.json 을 읽습니다.
실행: streamlit run streamlit_app.py
"""
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "docs" / "data" / "journals.json"
ISSN_RE = re.compile(r"^\d{4}-?\d{3}[\dXx]$")

st.set_page_config(page_title="저널 출판 기간 & APC 지원 안내", page_icon="🎓", layout="wide")


@st.cache_data
def load():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    rows = []
    for j in d["journals"]:
        ra, ap = j.get("rec_acc") or {}, j.get("acc_pub") or {}
        rows.append({
            "저널명": j["title"], "약어": j["abbrev"], "ISSN": j["issn"], "eISSN": j["eissn"],
            "출판사": j["publisher"], "투고→승인 중앙값(일)": ra.get("median"),
            "Q1": ra.get("q1"), "Q3": ra.get("q3"), "산출 논문 수": ra.get("n", 0),
            "승인→게재 중앙값(일)": ap.get("median"), "신뢰도": j["reliability"],
            "최근 승인일": j["latest_accepted"],
            "전남대 APC": "💡 지원 목록 일치" if j["apc"] else "목록에서 확인되지 않음",
        })
    return d["meta"], pd.DataFrame(rows)


def norm_issn(t):
    s = re.sub(r"[^0-9Xx]", "", t).upper()
    return f"{s[:4]}-{s[4:]}"


meta, df = load()
st.title("🎓 저널 출판 기간 & APC 지원 안내")
if df.empty:
    st.info("아직 수집된 데이터가 없습니다. GitHub Actions에서 수집을 먼저 실행해 주세요.")
    st.stop()
st.caption(f"업데이트 {meta.get('generated_at', '-')} · 저널 {meta.get('n_journals', 0):,}종")

q = st.text_area("저널명 · 약어 · ISSN · 출판사 (여러 개는 쉼표/줄바꿈/세미콜론)", height=70, placeholder="예) 2190-572X, 2374-7943 · PLOS ONE; ACS Omega · Wiley")
c1, c2, c3 = st.columns(3)
only_apc = c1.checkbox("전남대 APC 지원 목록 일치만")
max_days = c2.number_input("투고→승인 중앙값 N일 이내 (0=제한 없음)", 0, 2000, 0)
min_days = c3.number_input("N일 미만 제외 (0=제한 없음)", 0, 365, 0)

view, missing = df, []
tokens = [t for t in re.split(r"[\s,;]+", q.strip()) if t]
if tokens and all(ISSN_RE.match(t) for t in tokens):
    keys = [norm_issn(t) for t in tokens]
    view = df[df["ISSN"].isin(keys) | df["eISSN"].isin(keys)]
    found = set(view["ISSN"]) | set(view["eISSN"])
    missing = [k for k in keys if k not in found]
elif q.strip():
    parts = [p.strip().lower() for p in re.split(r"[,;\n]+", q) if p.strip()]
    mask = pd.Series(False, index=df.index)
    for p in parts:
        mask |= (df["저널명"].str.lower().str.contains(p, regex=False)
                 | df["약어"].str.lower().str.contains(p, regex=False)
                 | df["출판사"].str.lower().str.contains(p, regex=False))
    view = df[mask]
if only_apc:
    view = view[view["전남대 APC"].str.startswith("💡")]
if max_days:
    view = view[view["투고→승인 중앙값(일)"] <= max_days]
if min_days:
    view = view[view["투고→승인 중앙값(일)"] >= min_days]

st.markdown(f"💡 **{len(view):,}개 저널**")
for m in missing:
    st.warning(f"⚠️ {m}은(는) 현재 출판 기간 데이터베이스에 등록되어 있지 않습니다.")
st.dataframe(view.sort_values("투고→승인 중앙값(일)", na_position="last"), use_container_width=True, hide_index=True)
st.info("출판 기간은 저널별 최근 논문들의 투고→승인 일수 중앙값입니다. APC 지원은 ISSN/정확한 저널명이 지원 목록과 "
        "일치할 때만 표시합니다. 최신 지원 요건은 https://lib.jnu.ac.kr/webcontent/info/31 에서 확인하세요.")
