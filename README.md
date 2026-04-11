# 서울 구립 전자도서관 ebook 검색

서울시 19개 구립 전자도서관에서 ebook 대출 가능 여부를 한 번에 검색하는 도구입니다.

## 기능

- 책 제목 입력 → 19개 도서관 동시 검색
- 각 도서관별 보유 수량, 대출 중, 예약 대기 수 표시
- 대출 가능 여부 한눈에 확인 (🟢 가능 / 🔴 불가)
- 각 도서관 사이트 바로가기 링크 제공

## 검색 대상 도서관 (19개)

| 도서관 | 플랫폼 |
|--------|--------|
| 서울시립 전자도서관 | elib.seoul.go.kr |
| 강북구, 구로구, 노원구, 동대문구, 동작구, 서대문구, 서초구, 양천구, 용산구, 중구 | 교보문고 elibrary-front |
| 강동구, 강서구, 관악구, 송파구, 종로구, 영등포구, 성동구 | yes24/교보 |
| 강남구 | 자체 플랫폼 |

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
- requests + BeautifulSoup4 (스크래핑)
- ThreadPoolExecutor (병렬 검색)
