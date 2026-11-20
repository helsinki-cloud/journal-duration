"""오프라인 검증: NLM DTD 문서의 구조를 따른 '가상' XML + 가짜 NCBI 클라이언트.
실제 NCBI 데이터가 아닙니다. 실행: python -m pytest -q tests  (또는 python tests/test_pipeline.py)
"""
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import aggregate, collect, config as C  # noqa: E402
from pipeline.journals import load_all_journals, load_journals, load_table  # noqa: E402
from pipeline.parse import normalize_issn, parse_pubmed_xml  # noqa: E402


def article_xml(pmid, issn, title, rec, acc, epub=None, rev=None, ptype="Journal Article"):
    def d(tag, attr, date):
        if date is None:
            return ""
        y, m, dd = date.split("-")
        return f'<{tag} {attr}><Year>{y}</Year><Month>{m}</Month><Day>{dd}</Day></{tag}>'
    hist = d("PubMedPubDate", 'PubStatus="received"', rec) + d("PubMedPubDate", 'PubStatus="revised"', rev) \
        + d("PubMedPubDate", 'PubStatus="accepted"', acc) \
        + '<PubMedPubDate PubStatus="entrez"><Year>2026</Year><Month>5</Month><Day>13</Day></PubMedPubDate>'
    return f"""<PubmedArticle><MedlineCitation><PMID Version="1">{pmid}</PMID><Article>
      <Journal><ISSN IssnType="Electronic">{issn}</ISSN><Title>{title}</Title><ISOAbbreviation>{title[:10]}.</ISOAbbreviation></Journal>
      <ArticleTitle>t</ArticleTitle><PublicationTypeList><PublicationType>{ptype}</PublicationType></PublicationTypeList>
      {d("ArticleDate", 'DateType="Electronic"', epub)}</Article></MedlineCitation>
      <PubmedData><History>{hist}</History></PubmedData></PubmedArticle>"""


def test_normalize_issn():
    assert normalize_issn("00085472") == "0008-5472"
    assert normalize_issn("1234-567x") == "1234-567X"
    assert normalize_issn("abc") is None


def test_parse_dates_and_month_names():
    x = "<PubmedArticleSet>" + article_xml("1", "1111-1111", "Journal A", "2026-01-01", "2026-03-02",
                                           epub="2026-03-12", rev="2026-02-01") + "</PubmedArticleSet>"
    x = x.replace("<Month>03</Month><Day>12</Day>", "<Month>Mar</Month><Day>12</Day>")  # 영문 월
    r = parse_pubmed_xml(x.encode())[0]
    assert r["received"] == dt.date(2026, 1, 1) and r["accepted"] == dt.date(2026, 3, 2)
    assert r["epub"] == dt.date(2026, 3, 12) and r["revised"] == dt.date(2026, 2, 1)
    assert r["issn_electronic"] == "1111-1111"


class FakeClient:
    api_key = None

    def __init__(self, db):
        self.db = db          # issn -> list of (pmid, rec, acc, epub)
        self.fetched = []

    def esearch_pmids(self, term, mindate, maxdate, retmax):
        for issn, arts in self.db.items():
            if f'"{issn}"[is]' in term:
                ids = [a[0] for a in arts][:retmax]
                return ids, len(arts)
        return [], 0

    def efetch_pubmed_xml(self, pmids):
        self.fetched += pmids
        body = ""
        for issn, arts in self.db.items():
            for a in arts:
                if a[0] in pmids:
                    body += article_xml(a[0], issn, f"Journal {issn}", a[1], a[2], a[3])
        return f"<PubmedArticleSet>{body}</PubmedArticleSet>".encode()


def test_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        C.ARTICLES_CACHE = tmp / "articles.csv.gz"
        C.STATUS_CACHE = tmp / "status.csv"
        C.CACHE_DIR = tmp
        C.OUTPUT_JSON = tmp / "out.json"
        C.OUTPUT_CSV = tmp / "out.csv"
        C.MAX_PER_JOURNAL = 100

        # 입력 CSV: 하이픈 없는 ISSN, 한 칸에 ISSN 두 개 등 지저분한 형식 포함
        (tmp / "journals.csv").write_text(
            "Journal_Title,ISSN,Publisher\n"
            "Journal A,11111111,Pub A\n"
            "Journal B,2222-2222 / 3333-3333,Pub B\n"
            "Journal C,4444-4444,Pub C\n", encoding="utf-8-sig")
        (tmp / "apc.csv").write_text(
            "저널명,출판사,ISSN,eISSN\n"
            "Journal A,Pub A,1111-1111,\n"
            "Journal Bee,Pub B,9999-9999,\n", encoding="utf-8-sig")   # B는 비슷한 이름일 뿐 → 불일치여야 함
        journals = load_journals(tmp / "journals.csv")
        apc = load_table(tmp / "apc.csv")
        assert list(journals["jid"]) == ["1111-1111", "2222-2222", "4444-4444"]
        assert journals.loc[1, "eissn"] == "3333-3333"

        base = dt.date(2026, 1, 1)
        a_days = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 0, 5000]   # 0일·5000일은 제외 대상
        db = {
            "1111-1111": [(f"A{i}", str(base), str(base + dt.timedelta(d)), str(base + dt.timedelta(d + 10)))
                          for i, d in enumerate(a_days)],
            "3333-3333": [(f"B{i}", str(base), str(base + dt.timedelta(d)), None) for i, d in enumerate([3, 200])],
        }
        fake = FakeClient(db)
        arts, st = collect.run(client=fake, journals=journals, today=dt.date(2026, 11, 20), log=lambda *_: None)
        assert len(arts) == 14

        # 두 번째 실행: 새 논문 1편만 추가되면 그 1편만 efetch 해야 함 (증분)
        db["1111-1111"].insert(0, ("A_new", str(base), str(base + dt.timedelta(65)), None))
        fake.fetched = []
        arts, st = collect.run(client=fake, journals=journals, today=dt.date(2026, 11, 20), log=lambda *_: None)
        assert fake.fetched == ["A_new"], fake.fetched

        meta, out = aggregate.run(journals=journals, apc=apc, articles=arts, status=st)
        A, B, Cj = out
        # A: 유효 11편(30~120 + 65), 0일·5000일 제외 → 중앙값 70
        assert A["rec_acc"]["n"] == 11 and A["rec_acc"]["median"] == 70, A["rec_acc"]
        assert A["acc_pub"]["median"] == 10
        assert A["reliability"] == "보통"
        assert A["apc"] is True and A["apc_match"] == "ISSN"
        # B: eISSN으로 검색됨, 2편 → 신뢰도 낮음, 3일짜리는 '7일 미만'으로 집계
        assert B["rec_acc"]["n"] == 2 and B["rec_acc"]["short"] == 1 and B["reliability"] == "낮음"
        assert B["apc"] is False          # 비슷한 이름(Journal Bee)·같은 출판사여도 불일치
        assert Cj["rec_acc"] is None and Cj["n_sampled"] == 0
        data = json.loads(C.OUTPUT_JSON.read_text(encoding="utf-8"))
        assert data["meta"]["n_apc_matched"] == 1
        assert pd.read_csv(C.OUTPUT_CSV, encoding="utf-8-sig").shape[0] == 3
        # PMC 목록 + APC 전용 저널 합치기: Journal A는 겹침(ISSN), Journal Bee는 APC에만 있음
        allj = load_all_journals(tmp / "journals.csv", tmp / "apc.csv")
        assert len(allj) == 4 and list(allj["source"]) == ["PMC", "PMC", "PMC", "APC"]
        assert allj.iloc[3]["jid"] == "9999-9999"
        meta, out = aggregate.run(journals=allj, apc=apc, articles=arts, status=st)
        assert meta["n_apc_only"] == 1 and meta["n_apc_matched"] == 2
        bee = out[3]
        assert bee["apc"] and bee["source"] == "APC" and bee["checked"] is False and bee["rec_acc"] is None
        json.loads(C.OUTPUT_JSON.read_text(encoding="utf-8"))
        return data


if __name__ == "__main__":
    test_normalize_issn()
    test_parse_dates_and_month_names()
    test_end_to_end()
    print("모든 테스트 통과")
