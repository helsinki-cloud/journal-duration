# 🎓 저널 출판 기간 & APC 지원 안내 (v2)

전남대학교병원 의학도서실 · Gemini Gems 버전을 대체하는 **자동 업데이트 웹 서비스**

---

## 1. 기존 Gems 버전의 문제와 이번 설계의 해결책

| 기존 문제 | v2의 해결 방식 |
|---|---|
| 엑셀을 매번 만들어 Gems에 **수동 업로드** | GitHub Actions가 **매주 자동 수집 → 자동 배포** (사람 손 안 감) |
| 저널당 **최신 논문 1편**만 → 우연히 빠르거나 느린 논문에 좌우 | 저널당 **최근 최대 100편**(최근 2년 이내)을 모아 **중앙값 + 사분위(Q1~Q3)** 로 표시, 표본 수로 신뢰도 표시 |
| 플랫폼(Gems)이 없어지면 서비스도 사라짐 | **코드·데이터 모두 내 GitHub 저장소**에 있음. 어디로든 옮길 수 있음 |
| Streamlit은 안 쓰면 잠듦 | 결과를 미리 계산해 두는 구조라 **서버가 필요 없는 정적 웹(GitHub Pages)** 으로 배포 → 잠들 서버 자체가 없음 |
| LLM이 표를 만들 때 누락·환각 위험 | 검색·필터·APC 대조를 **코드(규칙)로 처리** → 같은 입력엔 항상 같은 결과, ISSN/정확한 저널명 일치만 인정 |

### 데이터 출처를 PMC → PubMed로 바꾼 이유
- PubMed 레코드에는 출판사가 제공한 `received`(투고) / `revised`(수정) / `accepted`(승인) 날짜가 `History`에 들어 있습니다 (NLM PubMed DTD 공식 문서).
- PubMed XML이 PMC 전문 XML보다 가볍고, PMC 오픈액세스 여부와 상관없이 조회됩니다.
- 출판사가 날짜를 제공하지 않는 저널은 PubMed든 PMC든 값이 없습니다. 이런 저널은 화면에 `-`로 표시되고, “산출 논문 수 0 / 수집 N편”으로 드러납니다.

---

## 2. 전체 구조

```
 ┌──────────────── GitHub 저장소 (내 계정) ────────────────┐
 │                                                          │
 │  data/input/journals.csv      ← 저널 목록 (3,290종)      │
 │  data/input/apc_journals.csv  ← 전남대 APC 지원 목록     │
 │                                                          │
 │  [GitHub Actions: 매주 일요일 자동 실행]                 │
 │    ① pipeline.collect   PubMed 검색·수집 (신규 논문만)   │
 │    ② pipeline.aggregate 중앙값·사분위 계산 + APC 대조    │
 │         └→ docs/data/journals.json / journals.csv        │
 │    ③ GitHub Pages 배포                                   │
 │                                                          │
 │  수집 캐시(논문 단위 원자료) → 'data-cache' 릴리스 첨부   │
 │  (git 이력이 커지지 않게 릴리스 파일로 보관)             │
 └──────────────────────────────────────────────────────────┘
                     │
                     ▼
     https://<아이디>.github.io/<저장소명>/   ← 연구자들이 접속
     (HTML+JS만으로 검색·필터·정렬, 서버 없음)
```

### 폴더 구성
```
journal-duration/
├─ pipeline/
│  ├─ config.py      설정 (수집 편수, 기간, 이상치 기준 등)
│  ├─ ncbi.py        NCBI API 호출 (초당 호출 제한·재시도)
│  ├─ parse.py       PubMed XML → 투고/수정/승인/온라인게재일
│  ├─ journals.py    입력 CSV/엑셀 읽기 (컬럼명 자동 인식)
│  ├─ collect.py     1단계 수집 (증분)
│  └─ aggregate.py   2단계 집계 + APC 대조 → 웹 데이터
├─ docs/             ← 웹 화면 (GitHub Pages가 이 폴더를 배포)
│  ├─ index.html · app.js · style.css
│  └─ data/journals.json · journals.csv
├─ streamlit_app.py  (선택) 같은 데이터를 Streamlit으로 보여주는 버전
├─ tests/test_pipeline.py
└─ .github/workflows/
   ├─ update.yml     매주 수집·집계·배포
   └─ pages.yml      화면(docs) 수정 시 즉시 재배포
```

---

## 3. 배포 플랫폼 비교 (2026-11 확인 기준)

| 플랫폼 | 잠듦(슬립) | 이 프로젝트 적합도 |
|---|---|---|
| **GitHub Pages (추천)** | 정적 파일이라 잠들 서버가 없음 | ◎ 결과를 미리 계산해 두는 구조와 딱 맞음. 무료(공개 저장소) |
| Streamlit Community Cloud | 트래픽 12시간 없으면 잠듦 (공식 문서) | △ 깨우는 데 시간이 걸리고, 깨우기 자동화도 단순 접속으로는 안 된다는 보고가 있음 |
| Hugging Face Spaces (무료 CPU) | 48시간 비활성 시 잠듦 (공식 문서). 최근 무료 CPU 정책 변경 불만 글도 있어 불확실 | △ |
| Cloudflare Pages / Netlify | 정적 호스팅이라 잠듦 없음 | ○ GitHub Pages 대신 쓸 수 있음 (docs 폴더 그대로 연결) |

**결론:** 데이터 수집은 GitHub Actions, 화면은 GitHub Pages. Streamlit은 내부 시연용으로만 남겨 둡니다(`streamlit_app.py`).

> ⚠️ GitHub 규칙: 공개 저장소에서 **60일간 활동이 없으면 예약 실행이 자동 중지**됩니다(GitHub 공식 문서).
> 이 워크플로는 매주 결과 파일(생성 시각 포함)을 커밋하므로 정상 운영 중에는 걸리지 않습니다.
> 그래도 수집이 연속 실패하면 커밋이 안 생길 수 있으니, 가끔 Actions 탭에서 초록색 체크를 확인하세요.

---

## 4. 처음 설정하기 (한 번만)

### 4-1. 준비물
1. **GitHub 계정** (개인 또는 기관)
2. **NCBI API 키** (무료) — NCBI 계정 → Account settings → API Key Management에서 발급.
   키 없이도 동작하지만 초당 3회 → 키 있으면 초당 10회로 수집이 약 3배 빨라집니다.

### 4-2. 저장소 만들기
1. GitHub에서 새 저장소(Public) 생성 → 이 폴더 내용을 그대로 업로드
2. `data/input/` 에 두 파일 넣기
   - `journals.csv` : 기존 `pmc_3290_journals_latest_pmcid.csv` 를 **그대로 이름만 바꿔** 넣어도 됩니다.
     (컬럼명에 `title`/`journal`/`저널` 이 들어간 열 = 저널명, `issn` 이 들어간 열 = ISSN 으로 자동 인식.
     `eissn`/`electronic` 이 들어간 열은 eISSN, `publisher`/`출판사` 는 출판사)
   - `apc_journals.csv` : 전남대 APC 지원 목록 (2026-11 제공본 2,167종 포함됨: Wiley 1,317 / Cambridge 417 / De Gruyter 294 / Karger 103 / RSC 36). 목록이 바뀌면 같은 형식으로 덮어쓰면 됩니다.
   - ISSN은 하이픈 유무·소문자 x 등 형식이 섞여 있어도 자동 정리됩니다.

### 4-3. 비밀값 등록
저장소 → Settings → Secrets and variables → Actions → New repository secret
- `NCBI_API_KEY` : 발급받은 키
- `NCBI_EMAIL` : 연락용 이메일 (NCBI 권장)

### 4-4. Pages 켜기
Settings → Pages → Build and deployment → Source: **GitHub Actions**

### 4-5. 첫 실행
1. Actions 탭 → “저널 출판 기간 데이터 자동 업데이트” → **Run workflow**
2. 먼저 `limit` 에 `30` 을 넣고 시험 실행 → 결과 웹페이지 확인
3. 문제없으면 `0`(전체)으로 다시 실행
   - 첫 전체 실행은 모든 저널을 처음 받으므로 오래 걸립니다(대략 1~3시간으로 **추정**, 실제 시간은 첫 실행 로그로 확인 필요).
     GitHub Actions 한 작업의 최대 실행 시간은 6시간이며, 워크플로에 340분 제한을 걸어 두었습니다.
   - 이후 매주 실행은 **새로 나온 논문만** 받으므로 훨씬 짧습니다.

### 4-6. (선택) 내 PC에서 먼저 돌려보기
```bash
pip install -r requirements.txt
set NCBI_API_KEY=발급키          # macOS/Linux: export NCBI_API_KEY=발급키
set LIMIT_JOURNALS=20
python -m pipeline.collect
python -m pipeline.aggregate
python -m http.server -d docs 8000   # 브라우저에서 http://localhost:8000
```

---

## 4-7. 다른 배포 방법

### Streamlit Community Cloud
1. 위 4-2 ~ 4-5까지 해서 `docs/data/journals.json`에 실제 데이터가 들어가 있어야 함
2. share.streamlit.io 에 GitHub 계정으로 로그인 → Create app
3. Repository: 이 저장소 / Branch: main / Main file path: `streamlit_app.py` → Deploy
4. 12시간 동안 접속이 없으면 잠듦. 매주 데이터 커밋이 있으면 그때 앱이 다시 배포됨

### Hugging Face (정적 Space, 무료)
HF 공식 문서상 Gradio/Docker(Streamlit 포함) Space는 유료 플랜이 필요하고 Static Space는 무료이므로 **Static** 으로 만듭니다.
1. huggingface.co/new-space → SDK: **Static** → 공개(Public) → Create
2. Files 탭 → Upload files → `docs` 폴더 **안의** `index.html`, `app.js`, `style.css`, `data` 폴더를 올림
3. 자동 업데이트: HF Settings → Access Tokens에서 Write 토큰 발급 →
   GitHub Secrets에 `HF_TOKEN`(토큰), `HF_SPACE`(예: `아이디/journal-duration`) 등록 → 매주 자동 동기화

## 5. 출판 기간 계산 방법 (연구자 안내용)

1. **표본**: 저널별로 PubMed 등록일 기준 최근 730일 이내 논문 중 최신 100편.
   리뷰·체계적 문헌고찰·사설·레터·코멘트·정오표·뉴스·프리프린트 등은 제외 (원저 위주).
2. **투고→승인 일수** = accepted − received
3. **이상치 처리**: 0일 이하(투고일=승인일 등 날짜 오류)와 1,095일(3년) 초과는 계산에서 제외.
   7일 미만은 제외하지 않고 “7일 미만 N편”으로 따로 표시.
4. **대표값**: 평균이 아니라 **중앙값**(극단값 영향이 적음) + **Q1~Q3**(가운데 50% 논문이 걸린 범위).
5. **신뢰도**: 계산에 쓰인 논문 수 30편 이상 ‘높음’ / 10~29편 ‘보통’ / 1~9편 ‘낮음’.
6. **승인→온라인 게재** = ArticleDate(Electronic) − accepted (참고용 보조 지표)

모든 기준값은 `pipeline/config.py` 에서 바꿀 수 있습니다.

## 6. 전남대 APC 지원 판별 규칙 (Gems 지침 그대로 코드화)
- ISSN(print/electronic, PubMed 레코드상의 ISSN 포함) 또는 **정확한 저널명**(대소문자·공백만 정리)이 지원 목록과 일치할 때만 “💡 지원 목록 일치”
- 출판사가 같거나 이름이 비슷한 것으로는 **절대 추정하지 않음** → “목록에서 확인되지 않음”
- 테스트(`tests/test_pipeline.py`)에 “비슷한 이름·같은 출판사인데 불일치” 사례가 들어 있습니다.

## 7. 화면에서 되는 것 (Gems의 입력 패턴 규칙 반영)
- ISSN 여러 개 입력(쉼표·공백·줄바꿈·세미콜론, 하이픈 없어도 됨) → 비교표 + 없는 ISSN은 “⚠️ 데이터베이스에 등록되어 있지 않습니다”
- 저널명·약어 여러 개(쉼표/세미콜론/줄바꿈 구분) → 정확히 일치하는 것 먼저, 그다음 부분 일치
- 초록처럼 긴 글을 붙여 넣으면 → S2Journal 안내
- 필터: APC 지원만 / 중앙값 N일 이내 / N일 미만 제외 / 신뢰도
- 모든 열 클릭 정렬, 결과는 200개씩 “더 보기”로 **전부** 볼 수 있고, 전체 CSV 다운로드 가능
- 페이지 하단에 필수 안내사항 고정

## 8. 알려진 한계 (솔직하게)
- 날짜는 **출판사가 PubMed에 제공한 값**입니다. 제공하지 않는 저널은 계산할 수 없습니다.
- `revised`는 PubMed에 보통 1개만 기록되어 **심사 라운드 수는 알 수 없습니다.**
- 투고 후 다른 저널에서 이관(transfer)된 논문, 특집호 초청 논문은 비정상적으로 짧게 나올 수 있습니다 → 중앙값과 ‘7일 미만’ 표시로 완화.
- 이 코드는 샘플 XML과 가짜 API로 **오프라인 검증만** 했습니다. 실제 NCBI 응답으로는 첫 시험 실행(limit 30)에서 꼭 확인하세요.

## 9. 다음 단계 아이디어
1. **분야(주제) 필터**: NLM Catalog의 Broad Subject Term을 붙이면 “종양학 저널 중 60일 이내” 같은 검색 가능
2. **추세**: 실행마다 저널별 중앙값을 기록해 두면 “최근 빨라지는/느려지는 저널” 표시 가능
3. **챗봇 기능 복원**: 필요하면 이 JSON을 근거 데이터로 하는 LLM 질의 기능을 덧붙일 수 있음 (계산·대조는 지금처럼 코드가 하고, LLM은 질문 해석만)
4. **기관 도메인 연결**: GitHub Pages에 병원/도서관 하위 도메인 연결 가능 (전산팀 DNS 설정 필요)
