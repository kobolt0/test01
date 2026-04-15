import streamlit as st
import requests
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

urllib3.disable_warnings()

# 페이지 설정
st.set_page_config(page_title="서울 전자도서관 검색", page_icon="📚", layout="wide")
st.title("📚 서울 구립 전자도서관 ebook 검색")
st.caption("서울 21개 도서관 자동 검색 + 6개 도서관 링크 제공")

# 검색 입력
keyword = st.text_input("책 제목을 입력하세요", placeholder="예: 프로젝트 헤일메리")
search_btn = st.button("검색", type="primary")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ── 플랫폼별 검색 함수 ──────────────────────────────────────────────────────────

def search_seoul_metropolitan(keyword):
    """서울시립 전자도서관 (elib.seoul.go.kr)"""
    params = {
        "libCode": "", "contentType": "EB", "searchKeyword": keyword,
        "searchOption": "ALL", "sortOption": "POPULAR", "innerSearchYN": "N",
        "innerKeyword": "", "currentCount": 1, "pageCount": 10,
        "loanable": "", "isTotal": False, "showType": "LIST", "searchCombine": "N",
    }
    resp = requests.get("https://elib.seoul.go.kr/api/contents/search",
                        headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    books = resp.json().get("ContentDataList", [])
    results = []
    for b in books:
        total = b.get("b2bCopys", 0)
        loaned = b.get("currentLoanCount", 0)
        reserve = b.get("reserveCnt", 0)
        results.append({
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "publisher": b.get("publisher", ""),
            "available": total - loaned,
            "total": total,
            "reserve": reserve,
            "cover": b.get("coverMSizeUrl") or b.get("coverUrl"),
        })
    return results


def search_elibrary_front(name, base_url, keyword):
    """교보문고 elibrary-front 플랫폼 (10개 구)"""
    params = {"schClst": "ctts", "schDvsn": "000", "schTxt": keyword, "orderByKey": ""}
    resp = requests.get(f"{base_url}/elibrary-front/search/searchList.ink",
                        headers=HEADERS, params=params, timeout=10, verify=False)
    html = resp.content.decode("utf-8", errors="replace")

    results = []
    # 책 목록 파싱
    books = re.findall(
        r'class="tit"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?'
        r'class="writer">([^<]+)<.*?'
        r'대출\s*:\s*<strong>(\d+)/(\d+)</strong>.*?'
        r'예약\s*:\s*<strong>(\d+)</strong>',
        html, re.DOTALL
    )
    for title, author, loaned, total, reserve in books:
        loaned, total, reserve = int(loaned), int(total), int(reserve)
        results.append({
            "title": title.strip(),
            "author": author.strip(),
            "available": total - loaned,
            "total": total,
            "reserve": reserve,
        })

    # 파싱 실패 시 간단한 방식으로 재시도
    if not results and keyword in html:
        titles = re.findall(r'class="tit"[^>]*>\s*<a[^>]*>\s*([^<]+)\s*</a>', html)
        loan_status = re.findall(r'대출\s*:\s*<strong>(\d+)/(\d+)</strong>.*?예약\s*.*?<strong>(\d+)</strong>', html, re.DOTALL)
        for i, title in enumerate(titles):
            if i < len(loan_status):
                loaned, total, reserve = int(loan_status[i][0]), int(loan_status[i][1]), int(loan_status[i][2])
                results.append({
                    "title": title.strip(),
                    "author": "",
                    "available": total - loaned,
                    "total": total,
                    "reserve": reserve,
                })
            else:
                results.append({"title": title.strip(), "author": "", "available": -1, "total": 0, "reserve": 0})
    return results


def search_yes24_style(name, base_url, keyword, encoding="utf-8"):
    """yes24/교보 /search 패턴 플랫폼"""
    if encoding == "euc-kr":
        encoded = quote(keyword.encode("euc-kr"))
        url = f"{base_url}/search?srch_order=title&src_key={encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
    else:
        resp = requests.get(f"{base_url}/search", headers=HEADERS,
                            params={"srch_order": "title", "src_key": keyword},
                            timeout=10, verify=False)
    html = resp.content.decode(encoding, errors="replace")

    results = []
    # 보유/대출/예약 파싱
    # <li>보유 <strong>N</strong></li> <li>대출 <strong>N</strong></li> <li>예약 <strong>N</strong></li>
    blocks = re.findall(
        r'class="tit"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?'
        r'class="stat".*?보유.*?<strong>(\d+)</strong>.*?대출.*?<strong>(\d+)</strong>.*?예약.*?<strong>(\d+)</strong>',
        html, re.DOTALL
    )
    for title, total, loaned, reserve in blocks:
        total, loaned, reserve = int(total), int(loaned), int(reserve)
        results.append({
            "title": title.strip(),
            "author": "",
            "available": total - loaned,
            "total": total,
            "reserve": reserve,
        })

    # 파싱 실패 시 더 넓은 패턴으로
    if not results:
        stat_blocks = re.findall(r'<div class="stat">.*?</div>', html, re.DOTALL)
        title_blocks = re.findall(r'class="tit"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
        for i, stat in enumerate(stat_blocks):
            nums = re.findall(r'<strong>(\d+)</strong>', stat)
            if len(nums) >= 3:
                total, loaned, reserve = int(nums[0]), int(nums[1]), int(nums[2])
                title = title_blocks[i].strip() if i < len(title_blocks) else "?"
                results.append({
                    "title": title,
                    "author": "",
                    "available": total - loaned,
                    "total": total,
                    "reserve": reserve,
                })
    return results


def search_sen_library(keyword):
    """서울시교육청 전자도서관 - 모바일 사이트 HTML 스크래핑"""
    # 모바일 사이트는 TLS 인증서 문제로 verify=False 필요
    headers = {**HEADERS, "Referer": "https://m.e-lib.sen.go.kr/"}
    resp = requests.get(
        "https://m.e-lib.sen.go.kr/0_ebook/list.php",
        headers=headers,
        params={"search_txt": keyword, "search_type": "title"},
        timeout=10,
        verify=False
    )
    resp.raise_for_status()
    html = resp.content.decode("utf-8", errors="replace")

    results = []
    # 책 제목 파싱
    titles = re.findall(r'class="[^"]*tit[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
    if not titles:
        titles = re.findall(r'<strong[^>]*class="[^"]*book[^"]*"[^>]*>([^<]+)</strong>', html)
    # 보유/대출/예약 파싱
    stats = re.findall(
        r'보유\D*(\d+).*?대출\D*(\d+).*?예약\D*(\d+)',
        html, re.DOTALL
    )
    for i, title in enumerate(titles):
        if i < len(stats):
            total, loaned, reserve = int(stats[i][0]), int(stats[i][1]), int(stats[i][2])
        else:
            total, loaned, reserve = 0, 0, 0
        results.append({
            "title": title.strip(),
            "author": "",
            "available": total - loaned,
            "total": total,
            "reserve": reserve,
        })
    return results


def search_gangnam(keyword):
    """강남구 (EUC-KR, /elibbook/book_info.asp)"""
    encoded = quote(keyword.encode("euc-kr"))
    url = f"https://ebook.gangnam.go.kr/elibbook/book_info.asp?search=title&strSearch={encoded}"
    resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
    html = resp.content.decode("euc-kr", errors="replace")

    results = []
    # 제목 + 상태 파싱
    titles = re.findall(r'class="book_title"[^>]*><a[^>]*>([^<]+)</a>', html)
    # close = 예약마감, current = 상태 텍스트
    statuses = re.findall(r'class="current([^"]*)"[^>]*>([^<]+)<', html)

    for i, title in enumerate(titles):
        status_text = "확인 필요"
        is_available = False
        for cls, txt in statuses[i*2:(i+1)*2] if len(statuses) > i else []:
            txt = txt.strip()
            if "마감" in txt or "불가" in txt:
                status_text = txt
            elif "대출" in txt.lower() or "가능" in txt:
                status_text = txt
                is_available = True
        results.append({
            "title": title.strip(),
            "author": "",
            "available": 1 if is_available else 0,
            "total": 1,
            "reserve": 0,
            "status_text": status_text,
        })
    return results


# ── 도서관 목록 ──────────────────────────────────────────────────────────────────

def elibrary_search_url(base, kw):
    return f"{base}/elibrary-front/search/searchList.ink?schClst=ctts&schDvsn=000&schTxt={quote(kw)}"

def yes24_search_url(base, kw):
    return f"{base}/search?srch_order=title&src_key={quote(kw)}"

def yes24_search_url_euckr(base, kw):
    return f"{base}/search?srch_order=title&src_key={quote(kw.encode('euc-kr'))}"

def gangnam_search_url(kw):
    return f"https://ebook.gangnam.go.kr/elibbook/book_info.asp?search=title&strSearch={quote(kw.encode('euc-kr'))}"

LIBRARIES = [
    {"name": "서울시립",
     "search_url": lambda kw: f"https://elib.seoul.go.kr/contents/search/content?t=EB&k={quote(kw)}",
     "func": lambda kw: search_seoul_metropolitan(kw)},
    # elibrary-front (교보 기반) 11개 구
    {"name": "강북구",   "search_url": lambda kw: elibrary_search_url("http://ebook.gblib.or.kr", kw),      "func": lambda kw: search_elibrary_front("강북구", "http://ebook.gblib.or.kr", kw)},
    {"name": "구로구",   "search_url": lambda kw: elibrary_search_url("https://ebook.guro.go.kr", kw),      "func": lambda kw: search_elibrary_front("구로구", "https://ebook.guro.go.kr", kw)},
    {"name": "노원구",   "search_url": lambda kw: elibrary_search_url("https://eb.nowonlib.kr", kw),        "func": lambda kw: search_elibrary_front("노원구", "https://eb.nowonlib.kr", kw)},
    {"name": "동대문구", "search_url": lambda kw: elibrary_search_url("http://e-book.l4d.or.kr", kw),       "func": lambda kw: search_elibrary_front("동대문구", "http://e-book.l4d.or.kr", kw)},
    {"name": "동작구",   "search_url": lambda kw: elibrary_search_url("https://ebook.dongjak.go.kr", kw),   "func": lambda kw: search_elibrary_front("동작구", "https://ebook.dongjak.go.kr", kw)},
    {"name": "서대문구", "search_url": lambda kw: elibrary_search_url("http://ebook.sdm.or.kr", kw),        "func": lambda kw: search_elibrary_front("서대문구", "http://ebook.sdm.or.kr", kw)},
    {"name": "서초구",   "search_url": lambda kw: elibrary_search_url("https://ebook.seocholib.or.kr", kw), "func": lambda kw: search_elibrary_front("서초구", "https://ebook.seocholib.or.kr", kw)},
    {"name": "성북구",   "search_url": lambda kw: elibrary_search_url("https://elibrary.sblib.seoul.kr", kw), "func": lambda kw: search_elibrary_front("성북구", "https://elibrary.sblib.seoul.kr", kw)},
    {"name": "양천구",   "search_url": lambda kw: elibrary_search_url("http://ebook.yangcheon.or.kr", kw),  "func": lambda kw: search_elibrary_front("양천구", "http://ebook.yangcheon.or.kr", kw)},
    {"name": "용산구",   "search_url": lambda kw: elibrary_search_url("http://ebook.yslibrary.or.kr", kw),  "func": lambda kw: search_elibrary_front("용산구", "http://ebook.yslibrary.or.kr", kw)},
    {"name": "중구",     "search_url": lambda kw: elibrary_search_url("https://ebook.junggulib.or.kr", kw), "func": lambda kw: search_elibrary_front("중구", "https://ebook.junggulib.or.kr", kw)},
    # /search 패턴 (UTF-8)
    {"name": "강동구",   "search_url": lambda kw: yes24_search_url("https://ebook.gdlibrary.or.kr", kw),    "func": lambda kw: search_yes24_style("강동구", "https://ebook.gdlibrary.or.kr", kw)},
    {"name": "강서구",   "search_url": lambda kw: yes24_search_url("https://ebook.gangseo.seoul.kr", kw),   "func": lambda kw: search_yes24_style("강서구", "https://ebook.gangseo.seoul.kr", kw)},
    {"name": "관악구",   "search_url": lambda kw: yes24_search_url("https://e-lib.gwanak.go.kr", kw),       "func": lambda kw: search_yes24_style("관악구", "https://e-lib.gwanak.go.kr", kw)},
    {"name": "송파구",   "search_url": lambda kw: yes24_search_url("https://ebook.splib.or.kr", kw),        "func": lambda kw: search_yes24_style("송파구", "https://ebook.splib.or.kr", kw)},
    {"name": "종로구",   "search_url": lambda kw: yes24_search_url("https://elib.jongno.go.kr", kw),        "func": lambda kw: search_yes24_style("종로구", "https://elib.jongno.go.kr", kw)},
    {"name": "영등포구", "search_url": lambda kw: yes24_search_url("https://ebook.ydplib.or.kr", kw),       "func": lambda kw: search_yes24_style("영등포구", "https://ebook.ydplib.or.kr", kw)},
    # /search 패턴 (EUC-KR)
    {"name": "성동구",   "search_url": lambda kw: yes24_search_url_euckr("http://ebook.sdlib.or.kr:8092", kw), "func": lambda kw: search_yes24_style("성동구", "http://ebook.sdlib.or.kr:8092", kw, "euc-kr")},
    # 강남구 특수
    {"name": "강남구",   "search_url": lambda kw: gangnam_search_url(kw), "func": lambda kw: search_gangnam(kw)},
    # 서울시교육청 전자도서관 (XML API)
    {"name": "서울시교육청", "search_url": lambda kw: f"https://e-lib.sen.go.kr/contents/search?searchWord={quote(kw)}", "func": lambda kw: search_sen_library(kw)},
]

# 자동 검색 불가 도서관 (플랫폼 미지원 또는 로그인 필요) - 링크만 제공
LINK_ONLY_LIBRARIES = [
    # 성북구와 같은 elibrary-front 기반이나 SSO/방화벽으로 직접 접근 불가
    {"name": "도봉구",       "search_url": lambda kw: "https://elib.dobong.kr/Kyobo_T3/Default.asp",                              "note": "교보 T3 플랫폼"},
    {"name": "마포구",       "search_url": lambda kw: "https://mplib.mapo.go.kr/mcl/MENU1062/CONT4005/contents.do",               "note": "SSO 기반"},
    {"name": "은평구",       "search_url": lambda kw: "https://epbook.eplib.or.kr/ebookPlatform/home/main.do",                    "note": "리브로피아/YES24"},
    {"name": "광진구",       "search_url": lambda kw: "http://gwangjin.dasangng.co.kr/FxLibrary/",                                "note": "북큐브 FxLibrary"},
    {"name": "금천구",       "search_url": lambda kw: "https://elib.geumcheonlib.seoul.kr/FxLibrary/",                            "note": "북큐브 FxLibrary"},
    {"name": "국회도서관",   "search_url": lambda kw: "https://ebook.nanet.go.kr/main",                                           "note": "전국민 무료 (최초 1회 방문)"},
]


def search_library(lib, keyword):
    """단일 도서관 검색 (예외 처리 포함)"""
    try:
        results = lib["func"](keyword)
        return lib["name"], results, None
    except Exception as e:
        return lib["name"], [], str(e)


# ── UI ──────────────────────────────────────────────────────────────────────────

if search_btn and keyword:
    st.markdown(f"**'{keyword}'** 검색 중... ({len(LIBRARIES)}개 도서관 동시 검색)")
    progress = st.progress(0)
    results_container = st.container()

    all_results = {}
    # 각 도서관의 검색 결과 직접 링크 생성
    lib_urls = {lib["name"]: lib["search_url"](keyword) for lib in LIBRARIES}
    errors = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(search_library, lib, keyword): lib["name"] for lib in LIBRARIES}
        completed = 0
        for future in as_completed(futures):
            name, results, error = future.result()
            completed += 1
            progress.progress(completed / len(LIBRARIES))
            if error:
                errors[name] = error
            else:
                all_results[name] = results

    progress.empty()

    # 결과 표시
    with results_container:
        # 책 있는 도서관만 필터
        found = {name: books for name, books in all_results.items() if books}
        not_found = [name for name, books in all_results.items() if not books]

        if not found:
            st.warning("검색 결과가 없습니다.")
        else:
            st.success(f"**{len(found)}개** 도서관에서 검색 결과를 찾았습니다.")

            for lib_name, books in found.items():
                lib_url = lib_urls.get(lib_name, "")
                with st.expander(f"📚 {lib_name} ({len(books)}권)", expanded=True):
                    if lib_url:
                        st.markdown(f"🔗 [도서관 검색 결과 바로가기]({lib_url})")
                    for book in books:
                        available = book.get("available", 0)
                        total = book.get("total", 0)
                        reserve = book.get("reserve", 0)
                        status_text = book.get("status_text", "")

                        if available > 0:
                            icon = "🟢"
                            status = f"대출 가능 ({available}/{total}권)"
                        elif available == 0 and total > 0:
                            icon = "🔴"
                            status = f"대출 불가 (예약 {reserve}명)"
                        elif status_text:
                            icon = "🔴"
                            status = status_text
                        else:
                            icon = "⚪"
                            status = "상태 미확인"

                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{book.get('title', '')}**")
                            if book.get("author"):
                                st.caption(book["author"])
                        with col2:
                            st.markdown(f"{icon} {status}")
                        st.divider()

        # 결과 없는 도서관
        if not_found:
            st.markdown(f"**검색 결과 없음:** {', '.join(not_found)}")

        # 오류 도서관
        if errors:
            with st.expander("⚠️ 접속 오류"):
                for name, err in errors.items():
                    st.text(f"{name}: {err}")

        # 자동 검색 불가 도서관 - 링크만 제공
        st.markdown("---")
        st.markdown("**직접 검색 필요한 도서관** (자동 조회 불가)")
        cols = st.columns(4)
        for i, lib in enumerate(LINK_ONLY_LIBRARIES):
            url = lib["search_url"](keyword)
            note = lib.get("note", "")
            with cols[i % 4]:
                st.markdown(f"[🔗 {lib['name']}]({url})")
                st.caption(note)

elif search_btn and not keyword:
    st.warning("책 제목을 입력해주세요.")
