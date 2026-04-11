# 서울 전자도서관 ebook 검색

서울 전자도서관에서 ebook 대출 가능 여부를 한 번에 검색하는 도구입니다.

## 기능

- 책 제목 입력 → 21개 도서관 동시 자동 검색
- 각 도서관별 보유 수량, 대출 중, 예약 대기 수 표시
- 대출 가능 여부 한눈에 확인 (🟢 가능 / 🔴 불가)
- 검색 결과 페이지 직접 링크 제공
- 자동 검색 불가 도서관 6곳은 링크로 제공

## 자동 검색 대상 도서관 (21개)

| 도서관 | 플랫폼 |
|--------|--------|
| 서울시립 전자도서관 | elib.seoul.go.kr (JSON API) |
| 강북구, 구로구, 노원구, 동대문구, 동작구, 서대문구, 서초구, 성북구, 양천구, 용산구, 중구 (11개) | 교보문고 elibrary-front |
| 강동구, 강서구, 관악구, 송파구, 종로구, 영등포구 (6개) | yes24/교보 /search |
| 성동구 | yes24 (EUC-KR) |
| 강남구 | 자체 플랫폼 |
| 서울시교육청 전자도서관 | e-lib.sen.go.kr (XML API) |

## 링크 제공 도서관 (6개, 자동 검색 불가)

| 도서관 | 비고 |
|--------|------|
| 도봉구 | 교보 T3 플랫폼 |
| 마포구 | SSO 기반 |
| 은평구 | 리브로피아/YES24 |
| 광진구 | 북큐브 FxLibrary |
| 금천구 | 북큐브 FxLibrary |
| 국회도서관 | 전국민 무료 (최초 1회 여의도 방문 필요) |

## 실행 방법

### 1. 가상환경 설치 (최초 1회)

```bash
python3 -m venv .venv
.venv/bin/pip install streamlit requests beautifulsoup4
```

### 2. 실행

```bash
.venv/bin/streamlit run app.py
```

브라우저에서 http://localhost:8501 접속

## 기술 스택

- Python 3
- Streamlit (UI)
- requests + BeautifulSoup4 + xml.etree (스크래핑/파싱)
- ThreadPoolExecutor (병렬 검색)
