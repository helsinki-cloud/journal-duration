
"""수집·집계 설정값. 환경변수로 덮어쓸 수 있습니다."""
import os
from pathlib import Path
 
ROOT = Path(__file__).resolve().parent.parent
 
# ── 입력 파일 (사용자가 넣는 파일) ─────────────────────────────
INPUT_JOURNALS = ROOT / "data" / "input" / "journals.csv"      # PMC 3,290 저널 목록
INPUT_APC = ROOT / "data" / "input" / "apc_journals.csv"       # 전남대 APC 지원 저널 목록
 
# ── 중간 캐시 (논문 단위 원자료, 증분 수집용) ──────────────────
CACHE_DIR = ROOT / "data" / "cache"
ARTICLES_CACHE = CACHE_DIR / "articles.csv.gz"
STATUS_CACHE = CACHE_DIR / "journal_status.csv"
 
# ── 웹에 공개되는 결과물 ───────────────────────────────────────
OUTPUT_JSON = ROOT / "docs" / "data" / "journals.json"
OUTPUT_CSV = ROOT / "docs" / "data" / "journals.csv"
 
# ── 수집 범위 ──────────────────────────────────────────────────
# 저널당 "최근 N편"을 모으되, PubMed 등록일 기준 최근 LOOKBACK_DAYS 이내 논문만.
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "730"))
MAX_PER_JOURNAL = int(os.getenv("MAX_PER_JOURNAL", "100"))
EFETCH_BATCH = 200
# PMC 저널 목록의 'Agreement Status'가 Active인 저널만 수집 (폐간·이전 제호 제외). 0이면 전체
ACTIVE_ONLY = os.getenv("ACTIVE_ONLY", "1") == "1"
# 테스트용: 앞에서부터 N개 저널만 처리 (0 = 전체)
LIMIT_JOURNALS = int(os.getenv("LIMIT_JOURNALS", "0"))
 
# 원저 위주로 보기 위해 제외할 논문 유형 (PubMed Publication Type)
EXCLUDE_PUBTYPES = [
    "review", "systematic review", "editorial", "letter", "comment",
    "published erratum", "news", "retraction of publication",
    "retracted publication", "preprint",
]
 
# ── 집계 규칙 ──────────────────────────────────────────────────
MIN_VALID_DAYS = 1        # 0일 이하(투고일=승인일 등)는 오류로 보고 제외
MAX_VALID_DAYS = 1095     # 3년 초과는 이상치로 제외
SHORT_DAYS = 7            # 7일 미만은 '초단기' 건수로 따로 표시 (제외는 안 함)
# 표본 수에 따른 신뢰도 라벨
RELIABILITY = [(30, "높음"), (10, "보통"), (1, "낮음")]
 
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "").strip() or None
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "").strip() or None
NCBI_TOOL = "jnuh-journal-duration"
 
