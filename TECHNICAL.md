# 기술 문서 — 서울 전자도서관 ebook 검색

## 전체 구조

```
app.py
├── 플랫폼별 검색 함수 (4종)
│   ├── search_seoul_metropolitan()  ← JSON API
│   ├── search_elibrary_front()      ← HTML 스크래핑
│   ├── search_yes24_style()         ← HTML 스크래핑
│   └── search_gangnam()             ← HTML 스크래핑 (EUC-KR)
├── LIBRARIES         (21개, 자동 검색)
├── LINK_ONLY_LIBRARIES (7개, 링크만 제공)
└── Streamlit UI + ThreadPoolExecutor 병렬 실행
```

---

## 플랫폼별 검색 방식

### 1. 서울시립 전자도서관 — JSON REST API

- **URL**: `GET https://elib.seoul.go.kr/api/contents/search`
- 서울시립만 공개 JSON API를 제공함
- 응답 `ContentDataList` 배열에서 바로 정형화된 데이터를 얻을 수 있음

```
요청 파라미터:
  contentType=EB, searchKeyword=검색어, searchOption=ALL,
  currentCount=1, pageCount=10, sortOption=POPULAR

응답 필드:
  title, author, publisher
  b2bCopys      → 총 소장 수
  currentLoanCount → 현재 대출 중 수
  reserveCnt    → 예약 대기 수
  대출 가능 = b2bCopys - currentLoanCount
```

---

### 2. 교보문고 elibrary-front 플랫폼 — HTML 스크래핑 (11개 구)

해당 구: 강북, 구로, 노원, 동대문, 동작, 서대문, 서초, 성북, 양천, 용산, 중구

- **URL 패턴**: `{도메인}/elibrary-front/search/searchList.ink`
- **파라미터**: `schClst=ctts, schDvsn=000, schTxt=검색어`
- 11개 구가 모두 동일한 엔드포인트와 HTML 구조를 사용하므로 함수 하나로 처리

HTML에서 정규식으로 추출:
```
class="tit" → 제목
class="writer" → 저자
대출 : <strong>N/N</strong> → 대출수/총보유수
예약 : <strong>N</strong> → 예약대기수
```

1차 패턴 실패 시 더 단순한 패턴으로 재시도하는 폴백 로직 포함.

> SSL 인증서 문제가 있는 구가 있어 `verify=False` 사용.
> urllib3 경고 억제: `urllib3.disable_warnings()`

---

### 3. yes24/교보 /search 패턴 — HTML 스크래핑 (6개 구)

해당 구: 강동, 강서, 관악, 송파, 종로, 영등포

- **URL 패턴**: `{도메인}/search?srch_order=title&src_key=검색어`
- elibrary-front와 다른 HTML 구조지만 동일한 yes24 기반 플랫폼

HTML에서 정규식으로 추출:
```
class="tit" → 제목
class="stat" 안의 보유/대출/예약 <strong>N</strong>
```

stat 블록 파싱 실패 시 폴백 패턴으로 재시도.

#### 성동구 — EUC-KR 인코딩 예외

성동구(`http://ebook.sdlib.or.kr:8092`)는 동일한 yes24 /search 패턴이지만 페이지 인코딩이 EUC-KR.

```python
# EUC-KR 처리: URL 인코딩 시 euc-kr 바이트로 변환
encoded = quote(keyword.encode("euc-kr"))
url = f"{base_url}/search?srch_order=title&src_key={encoded}"
resp.content.decode("euc-kr", errors="replace")
```

---

### 4. 강남구 자체 플랫폼 — HTML 스크래핑 (EUC-KR)

- **URL**: `https://ebook.gangnam.go.kr/elibbook/book_info.asp`
- **파라미터**: `search=title, strSearch=검색어(EUC-KR 인코딩)`
- 타 구와 다른 독자 플랫폼, 응답도 EUC-KR

HTML 구조가 다름:
```
class="book_title" → 제목
class="current{...}" → 대출 상태 텍스트 ("대출가능", "예약마감" 등)
```
숫자 기반 보유/대출 수 대신 상태 텍스트로 표시.

---

## 병렬 검색 — ThreadPoolExecutor

21개 도서관을 순차적으로 조회하면 HTTP 타임아웃(각 10초)만 해도 최대 210초 소요.
`ThreadPoolExecutor(max_workers=10)`으로 동시 실행해 전체 대기 시간을 단도서관 수준(~10초)으로 단축.

```python
futures = {executor.submit(search_library, lib, keyword): lib["name"] for lib in LIBRARIES}
for future in as_completed(futures):
    name, results, error = future.result()
    progress.progress(completed / len(LIBRARIES))  # 진행률 실시간 표시
```

`as_completed()`로 완료되는 순서대로 결과를 받아 Streamlit 진행 바(progress bar)를 업데이트.

---

## URL 인코딩

모든 검색어는 URL에 삽입되기 전 `urllib.parse.quote()`로 인코딩.

```python
from urllib.parse import quote

# UTF-8 인코딩 (기본)
quote("헤일메리")  →  "%ED%97%A4%EC%9D%BC%EB%A9%94%EB%A6%AC"

# EUC-KR 인코딩 (강남구, 성동구)
quote("헤일메리".encode("euc-kr"))  →  "%C7%EC%C0%CF%B8%DE%B8%AE"
```

---

## 자동 검색 불가 도서관 (LINK_ONLY_LIBRARIES)

7개 도서관은 자동 조회 대신 클릭 가능한 링크만 제공. 사유:

| 도서관 | 사유 |
|--------|------|
| 도봉구 | Kyobo T3 플랫폼 — 검색이 JS 폼 POST 방식 |
| 마포구 | SSO 로그인 필수, 비인증 요청 차단 |
| 은평구 | 리브로피아/YES24 — 검색 엔드포인트 JS 동적 생성 |
| 광진구 | 북큐브 FxLibrary — TLS 인증서 오류 + JS POST |
| 금천구 | 북큐브 FxLibrary — URL 파라미터 무시, JS POST만 동작 |
| 서울시교육청 | 스크래핑 차단 (API 파라미터 무시, HTML 반환 502) |
| 국회도서관 | SPA(JavaScript 렌더링) — 직접 API 없음 |

가능한 도서관은 검색어가 포함된 직접 검색 결과 URL로 연결:
```python
# 예: 서울시교육청
f"https://e-lib.sen.go.kr/contents/search?type=&searchOpt=0&searchKeyword={quote(kw)}"

# 예: 국회도서관
f"https://ebook.nanet.go.kr/contents/search?searchKeyword={quote(kw)}&type=EB"
```

---

## 데이터 흐름

```
사용자 입력 (Streamlit text_input)
    ↓
ThreadPoolExecutor: 21개 도서관 동시 HTTP 요청
    ↓                           ↓
JSON 파싱 (서울시립)       HTML 스크래핑 + 정규식 (나머지)
    ↓
정규화된 딕셔너리:
  { title, author, available, total, reserve }
    ↓
Streamlit UI:
  🟢 대출 가능 (available > 0)
  🔴 대출 불가 (available == 0)
  ⚪ 상태 미확인
    +
링크 전용 도서관 7개 (버튼 형태)
```

---

## 의존 패키지

| 패키지 | 용도 |
|--------|------|
| streamlit | 웹 UI |
| requests | HTTP 요청 |
| re (표준 라이브러리) | HTML 정규식 파싱 |
| urllib.parse (표준 라이브러리) | URL 인코딩 |
| concurrent.futures (표준 라이브러리) | 병렬 실행 |
| urllib3 (표준 라이브러리) | SSL 경고 억제 |

BeautifulSoup4는 설치되어 있으나 현재 코드에서는 미사용. 정규식만으로 파싱 가능해 불필요.
