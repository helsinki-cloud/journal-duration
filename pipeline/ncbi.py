"""NCBI E-utilities 클라이언트 (속도 제한 + 재시도).

- API 키 없음: 초당 3회 / 있음: 초당 10회 (NCBI 공식 정책)
"""
import time

import requests

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


class NCBIClient:
    def __init__(self, api_key=None, email=None, tool="jnuh-journal-duration",
                 max_retries=5, timeout=60):
        self.api_key = api_key
        self.email = email
        self.tool = tool
        self.max_retries = max_retries
        self.timeout = timeout
        # 한도보다 약간 여유 있게
        self.min_interval = 0.12 if api_key else 0.36
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"{tool} (+https://github.com)"

    def _throttle(self):
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _common(self):
        p = {"tool": self.tool}
        if self.api_key:
            p["api_key"] = self.api_key
        if self.email:
            p["email"] = self.email
        return p

    def _request(self, endpoint, params, method="GET"):
        params = {**self._common(), **params}
        url = BASE + endpoint
        last_err = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                if method == "POST":
                    r = self.session.post(url, data=params, timeout=self.timeout)
                else:
                    r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 200:
                    return r
                last_err = f"HTTP {r.status_code}"
                # 429(과다요청)·5xx는 대기 후 재시도
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            except requests.RequestException as e:
                last_err = str(e)
            time.sleep(2 ** attempt)
        raise RuntimeError(f"NCBI {endpoint} 실패: {last_err}")

    def esearch_pmids(self, term, mindate, maxdate, retmax):
        """조건에 맞는 PMID 목록 (최신 출판 순)."""
        r = self._request("esearch.fcgi", {
            "db": "pubmed", "term": term, "retmode": "json",
            "retmax": retmax, "sort": "pub_date",
            "datetype": "edat", "mindate": mindate, "maxdate": maxdate,
        })
        res = r.json().get("esearchresult", {})
        if "ERROR" in res:
            raise RuntimeError(res["ERROR"])
        return res.get("idlist", []), int(res.get("count", 0))

    def efetch_pubmed_xml(self, pmids):
        """PMID 묶음의 PubMed XML (POST: 긴 ID 목록도 안전)."""
        r = self._request("efetch.fcgi", {
            "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        }, method="POST")
        return r.content
