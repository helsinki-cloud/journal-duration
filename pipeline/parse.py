"""PubMed XML → 논문별 날짜 정보.

PubMed 레코드의 PubmedData/History 에는 출판사가 제공한
received(투고) / revised(수정) / accepted(승인) 날짜가 들어 있고,
Article/ArticleDate[@DateType='Electronic'] 에 온라인 게재일이 들어 있습니다.
(NLM PubMed DTD 문서 기준. 출판사가 제공하지 않으면 해당 날짜는 비어 있습니다.)
"""
import datetime as dt
import re
import xml.etree.ElementTree as ET

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def normalize_issn(value):
    """'00085472', '0008 5472', '0008-547x' → '0008-547X'. 형식이 아니면 None."""
    if value is None:
        return None
    s = re.sub(r"[^0-9Xx]", "", str(value)).upper()
    if len(s) != 8 or not s[:7].isdigit():
        return None
    return f"{s[:4]}-{s[4:]}"


def _to_date(node):
    """<Year><Month><Day> 노드 → date. 일(Day)까지 없으면 None (일수 계산 불가)."""
    if node is None:
        return None
    y, m, d = node.findtext("Year"), node.findtext("Month"), node.findtext("Day")
    if not (y and m and d):
        return None
    try:
        m = m.strip()
        month = int(m) if m.isdigit() else MONTHS.get(m[:3].lower())
        return dt.date(int(y), int(month), int(d))
    except (TypeError, ValueError):
        return None


def parse_pubmed_xml(xml_bytes):
    rows = []
    root = ET.fromstring(xml_bytes)
    for art in root.iter("PubmedArticle"):
        mc = art.find("MedlineCitation")
        if mc is None:
            continue
        pmid = (mc.findtext("PMID") or "").strip()
        a = mc.find("Article")
        j = a.find("Journal") if a is not None else None

        issn_p = issn_e = None
        if j is not None:
            for n in j.findall("ISSN"):
                t = n.attrib.get("IssnType", "").lower()
                if t == "print":
                    issn_p = normalize_issn(n.text)
                elif t == "electronic":
                    issn_e = normalize_issn(n.text)

        hist = {}
        for n in art.findall("PubmedData/History/PubMedPubDate"):
            status = n.attrib.get("PubStatus")
            d = _to_date(n)
            if d is None:
                continue
            # revised 가 여러 번이면 가장 이른 것(1차 수정본)
            if status not in hist or (status == "revised" and d < hist[status]):
                hist[status] = d

        epub = None
        if a is not None:
            for n in a.findall("ArticleDate"):
                if n.attrib.get("DateType", "").lower() == "electronic":
                    epub = _to_date(n)
                    break
        if epub is None:
            epub = hist.get("epublish") or hist.get("aheadofprint")

        pubtypes = [p.text.strip() for p in mc.findall("Article/PublicationTypeList/PublicationType") if p.text]

        rows.append({
            "pmid": pmid,
            "journal_title": (j.findtext("Title") or "").strip() if j is not None else "",
            "iso_abbrev": (j.findtext("ISOAbbreviation") or "").strip() if j is not None else "",
            "issn_print": issn_p,
            "issn_electronic": issn_e,
            "received": hist.get("received"),
            "revised": hist.get("revised"),
            "accepted": hist.get("accepted"),
            "epub": epub,
            "pubtypes": "|".join(pubtypes),
        })
    return rows
