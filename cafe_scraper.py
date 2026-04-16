"""
네이버 카페 회원 목록 + 게시판 집계 Selenium 스크래퍼
- 회원 관리 페이지: id="_sortPerPage"로 100명 정렬
- 게시판 URL: https://cafe.naver.com/f-e/cafes/{club_id}/menus/{menu_id}?page=N&size=50
"""

import json
import time
import re
import datetime
import calendar
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup

NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
CAFE_BASE_URL = "https://cafe.naver.com"


class CafeScraper:
    def __init__(self, cafe_name, on_status=None):
        self.cafe_name = cafe_name
        self.cafe_url = f"{CAFE_BASE_URL}/{cafe_name}"
        self.club_id = None
        self.driver = None
        self._on_status = on_status or (lambda msg: print(f"[스크래퍼] {msg}"))

    def _status(self, msg):
        self._on_status(msg)

    # ──────────────────────────────────────────────
    # 브라우저 / 로그인
    # ──────────────────────────────────────────────

    def start(self):
        self._status("Chrome 브라우저를 시작합니다...")
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--lang=ko-KR")
        options.add_argument("--window-size=1200,900")
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})

    def open_login_page(self):
        self._status("네이버 로그인 페이지로 이동합니다. 직접 로그인해 주세요.")
        self.driver.get(NAVER_LOGIN_URL)

    def wait_for_login(self, timeout=300):
        self._status(f"로그인 대기 중... (최대 {timeout // 60}분)")
        start = time.time()
        while time.time() - start < timeout:
            try:
                url = self.driver.current_url
                if "nidlogin" not in url and "nid.naver.com" not in url:
                    self._status("로그인 성공!")
                    time.sleep(1)
                    return True
                for c in self.driver.get_cookies():
                    if c['name'] == 'NID_AUT':
                        self._status("로그인 성공! (쿠키 감지)")
                        time.sleep(1)
                        return True
            except Exception:
                pass
            time.sleep(2)
        self._status("로그인 시간 초과!")
        return False

    def get_club_id(self, config_club_id=None):
        """clubId 설정. config에서 받거나 카페 페이지에서 추출."""
        if config_club_id:
            self.club_id = str(config_club_id)
            self._status(f"카페 ID (설정값): {self.club_id}")
            return self.club_id

        self._status(f"카페 페이지 접속 중: {self.cafe_url}")
        self.driver.get(self.cafe_url)
        time.sleep(3)
        page_source = self.driver.page_source
        for pattern in [r'clubid["\s]*[:=]\s*["\']?(\d+)', r'cafeId["\s]*[:=]\s*["\']?(\d+)',
                        r'clubid=(\d+)']:
            match = re.search(pattern, page_source, re.IGNORECASE)
            if match:
                self.club_id = match.group(1)
                self._status(f"카페 ID 발견: {self.club_id}")
                return self.club_id
        try:
            cid = self.driver.execute_script(
                "return typeof g_clubid !== 'undefined' ? g_clubid : "
                "(typeof window.clubid !== 'undefined' ? window.clubid : null)")
            if cid:
                self.club_id = str(cid)
                self._status(f"카페 ID 발견 (JS): {self.club_id}")
                return self.club_id
        except Exception:
            pass
        self._status("카페 ID를 찾을 수 없습니다!")
        return None

    # ──────────────────────────────────────────────
    # 게시판 스크래핑 (새 URL 구조)
    # URL: https://cafe.naver.com/f-e/cafes/{club_id}/menus/{menu_id}?page=N&size=50
    # ──────────────────────────────────────────────

    @staticmethod
    def _calc_end_date(start_date):
        next_month = start_date.month % 12 + 1
        next_year = start_date.year + (1 if start_date.month == 12 else 0)
        last_day = calendar.monthrange(next_year, next_month)[1]
        end_day = min(start_date.day, last_day)
        return datetime.date(next_year, next_month, end_day)

    def scrape_board_posts(self, menu_id, start_date_str, end_date_str=None,
                           nickname_to_id=None, id_set=None, board_label="게시판"):
        """
        게시판에서 날짜 범위 내 작성자별 게시글 수 집계.
        start_date_str: 시작일 'YYYY-MM-DD'
        end_date_str: 종료일 'YYYY-MM-DD' (None이면 시작일+1개월)
        """
        if not self.club_id:
            return {}

        nickname_to_id = nickname_to_id or {}
        id_set = id_set or set(nickname_to_id.values())
        start_date = datetime.date.fromisoformat(start_date_str)
        if end_date_str:
            end_date = datetime.date.fromisoformat(end_date_str)
        else:
            end_date = self._calc_end_date(start_date)

        def make_url(pg):
            return (f"{CAFE_BASE_URL}/f-e/cafes/{self.club_id}"
                    f"/menus/{menu_id}?page={pg}&size=50")

        self._status(f"{board_label} 스크래핑 시작 ({start_date_str}~{end_date.isoformat()})...")
        self.driver.get(make_url(1))
        time.sleep(4)

        # 1달 이상 과거이면 빠르게 건너뛰기 모드
        today = datetime.date.today()
        is_old = (today - end_date).days > 30
        skip_phase = is_old  # True면 10페이지씩 건너뛰기 단계
        backtrack_page = None  # 너무 많이 건너뛴 경우 되돌아올 페이지

        author_counts = {}
        page = 1
        found_range = False
        found_older = False
        empty_pages = 0
        oldest_date_seen = None
        unresolved = 0
        skipped = 0

        while not found_older:
            if skip_phase:
                self._status(f"{board_label} 빠른 탐색 {page}p → 범위 찾는 중...")
            else:
                self._status(f"{board_label} {page}p (누적: {sum(author_counts.values())}건)")

            if page > 1:
                self.driver.get(make_url(page))
                time.sleep(3)

            self.driver.switch_to.default_content()
            time.sleep(1)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            articles = self._extract_article_rows(soup)

            if not articles:
                empty_pages += 1
                if empty_pages >= 2:
                    break
                page += 1
                continue

            empty_pages = 0

            # 이 페이지의 최신/최구 날짜 파악
            page_newest = None
            page_oldest = None
            for article in articles:
                d = article.get('date', '')
                if article.get('is_notice') or not d:
                    continue
                ay, am, ad = self._parse_article_date(d, start_date.year)
                if ay == 0:
                    continue
                try:
                    art_date = datetime.date(ay, am, ad)
                except ValueError:
                    continue
                if page_newest is None or art_date > page_newest:
                    page_newest = art_date
                if page_oldest is None or art_date < page_oldest:
                    page_oldest = art_date
                if oldest_date_seen is None or art_date < oldest_date_seen:
                    oldest_date_seen = art_date

            # ── 빠른 건너뛰기 단계 ──
            if skip_phase and page_oldest:
                if page_oldest > end_date:
                    # 아직 범위보다 미래 → button.btn.type_next로 10페이지 건너뛰기
                    self._status(f"{board_label} {page}p: {page_oldest} > {end_date} → 10p 건너뛰기")
                    jumped = self._click_skip_button()
                    if jumped:
                        page += 10
                        time.sleep(2)
                        continue
                    else:
                        # 건너뛰기 버튼 없음 → 1페이지씩
                        skip_phase = False

                elif page_oldest < start_date and page_newest and page_newest < start_date:
                    # 너무 많이 건너뛰었음 (범위를 지나침) → 되돌아가기
                    self._status(f"{board_label} 너무 많이 건너뜀 → 1p씩 되돌아가기")
                    skip_phase = False
                    # 10페이지 전으로 돌아가서 1페이지씩 확인
                    page = max(1, page - 10)
                    self.driver.get(make_url(page))
                    time.sleep(3)
                    continue
                else:
                    # 범위에 도달 → 정밀 탐색으로 전환
                    skip_phase = False

            # ── 정밀 탐색 단계 (1페이지씩) ──
            for article in articles:
                art_date_str = article.get('date', '')
                nickname = article.get('nickname', '').strip()

                if article.get('is_notice') or not art_date_str:
                    continue

                ay, am, ad = self._parse_article_date(art_date_str, start_date.year)
                if ay == 0:
                    continue

                try:
                    art_date = datetime.date(ay, am, ad)
                except ValueError:
                    continue

                if start_date <= art_date <= end_date:
                    # 1단계: 닉네임으로 바로 매칭
                    naver_id = nickname_to_id.get(nickname, '')

                    if naver_id:
                        author_counts[naver_id] = author_counts.get(naver_id, 0) + 1
                        found_range = True
                    else:
                        # 2단계: 미매칭 → 프로필 확인
                        unresolved += 1
                        self._status(f"닉네임 '{nickname}' 미매칭 → 프로필 확인...")
                        found_id = self._get_user_id_via_profile(nickname)

                        if found_id and found_id in id_set:
                            nickname_to_id[nickname] = found_id
                            author_counts[found_id] = author_counts.get(found_id, 0) + 1
                            found_range = True
                        else:
                            skipped += 1
                            if found_id:
                                nickname_to_id[nickname] = found_id

                elif art_date < start_date:
                    found_older = True
                    break

            if not found_older:
                page += 1
                if page > 1000:
                    break

        if not found_range and oldest_date_seen and start_date < oldest_date_seen:
            err = (f"설정한 날짜({start_date_str})가 가장 오래된 글"
                   f"({oldest_date_seen.isoformat()})보다 과거입니다.")
            self._status(f"오류: {err}")
            return f"ERROR:{err}"

        total = sum(author_counts.values())
        self._status(f"{board_label} 완료: {len(author_counts)}명, {total}건 "
                     f"(프로필확인 {unresolved}회, 무시 {skipped}건)")
        return author_counts

    def _click_skip_button(self):
        """button.btn.type_next 클릭하여 10페이지 건너뛰기. 성공 시 True."""
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, 'button.btn.type_next')
            if btn.is_displayed() and btn.is_enabled():
                btn.click()
                time.sleep(2)
                return True
        except Exception:
            pass
        # 폴백: 텍스트로 찾기
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button.btn')
            for btn in buttons:
                if btn.get_attribute('class') and 'type_next' in btn.get_attribute('class'):
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(2)
                        return True
        except Exception:
            pass
        return False

    def _extract_article_rows(self, soup):
        """게시글 목록에서 닉네임, 날짜, URL 추출"""
        articles = []
        article_rows = []

        # 새 URL 구조의 게시글 행 찾기
        for sel in ['.article-board tr', 'table.board-list tr',
                    '#upperArticleList tr', '.board_box tr',
                    'table tr', '.article_lst li']:
            rows = soup.select(sel)
            if len(rows) > 2:
                article_rows = rows
                break

        if not article_rows:
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if len(rows) > 3:
                    article_rows = rows
                    break

        for row in article_rows:
            nickname = ''
            date_str = ''
            article_url = ''
            author_link = ''
            is_notice = False

            row_class = ' '.join(row.get('class', []))
            if 'notice' in row_class.lower() or 'head' in row_class.lower():
                is_notice = True
            notice_elem = row.find(class_=re.compile(r'notice|board-tag-txt'))
            if notice_elem and '공지' in notice_elem.get_text(strip=True):
                is_notice = True

            if row.find('th') and not row.find('td'):
                continue

            # 게시글 URL
            for link in row.find_all('a', href=True):
                href = link.get('href', '')
                if ('ArticleRead' in href or 'articleid' in href.lower()
                        or re.search(r'/articles/\d+', href)):
                    if href.startswith('/'):
                        article_url = f"{CAFE_BASE_URL}{href}"
                    elif href.startswith('http'):
                        article_url = href
                    else:
                        article_url = f"{CAFE_BASE_URL}/{href}"
                    break

            # 닉네임 추출: span.nickname 우선
            nick_span = row.find('span', class_='nickname')
            if nick_span:
                nickname = nick_span.get_text(strip=True)
                # 부모 링크에서 author_link 추출
                parent_a = nick_span.find_parent('a', href=True)
                if parent_a:
                    href = parent_a.get('href', '')
                    author_link = href if href.startswith('http') else f"{CAFE_BASE_URL}{href}"

            # 폴백: td.p-nick, td.writer 등
            if not nickname:
                for td in row.find_all('td'):
                    td_class = ' '.join(td.get('class', []))
                    if 'p-nick' in td_class or 'writer' in td_class.lower():
                        nickname = td.get_text(strip=True)
                        a = td.find('a', href=True)
                        if a:
                            href = a.get('href', '')
                            author_link = href if href.startswith('http') else f"{CAFE_BASE_URL}{href}"
                        break

            if not nickname:
                for link in row.find_all('a', href=True):
                    href = link.get('href', '')
                    if ('MemberInfo' in href or 'profile' in href.lower()
                            or 'memberid' in href):
                        txt = link.get_text(strip=True)
                        if txt and not txt.isdigit():
                            nickname = txt
                            author_link = href if href.startswith('http') else f"{CAFE_BASE_URL}{href}"
                            break

            # 날짜
            for elem in row.find_all(class_=re.compile(r'date|time|td_date|regDate')):
                txt = elem.get_text(strip=True)
                if txt:
                    date_str = txt
                    break
            if not date_str:
                for cell in row.find_all(['td', 'span', 'div']):
                    t = cell.get_text(strip=True)
                    if re.match(r'^\d{4}\.\d{2}\.\d{2}', t):
                        date_str = t
                        break
                    if re.match(r'^\d{2}\.\d{2}\.?\s*$', t):
                        date_str = t
                        break
                    if re.match(r'^\d{1,2}:\d{2}$', t):
                        date_str = t
                        break

            if nickname or article_url:
                articles.append({
                    'nickname': nickname, 'date': date_str,
                    'article_url': article_url, 'author_link': author_link,
                    'is_notice': is_notice
                })

        return articles

    # ──────────────────────────────────────────────
    # 작성자 ID 추출
    # ──────────────────────────────────────────────

    def _get_user_id_via_profile(self, nickname):
        """
        게시판 목록에서 작성자 닉네임을 클릭 → 프로필 레이어 →
        "게시글 보기" 버튼 클릭 → span.user_id 추출.
        닉네임을 못 찾으면 빈 문자열 반환.
        """
        try:
            self.driver.switch_to.default_content()

            # 1) 게시판 목록에서 span.nickname 중 해당 닉네임 클릭
            nick_elements = self.driver.find_elements(By.CSS_SELECTOR, 'span.nickname')
            clicked = False
            for elem in nick_elements:
                try:
                    if elem.text.strip() == nickname and elem.is_displayed():
                        elem.click()
                        clicked = True
                        break
                except Exception:
                    continue

            # span.nickname으로 못 찾으면 링크 텍스트로 시도
            if not clicked:
                links = self.driver.find_elements(By.CSS_SELECTOR,
                    'td.p-nick a, td[class*="writer"] a, a[class*="nick"]')
                for link in links:
                    try:
                        if link.text.strip() == nickname and link.is_displayed():
                            link.click()
                            clicked = True
                            break
                    except Exception:
                        continue

            if not clicked:
                return ''

            time.sleep(2)

            # 2) 프로필 레이어에서 "게시글 보기" 버튼 클릭
            try:
                view_btn = self.driver.find_element(
                    By.XPATH, "//button[contains(text(),'게시글 보기')]")
                view_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                # 버튼 못 찾으면 레이어에서 직접 span.user_id 시도
                try:
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    nid = self._find_user_id_in_soup(soup)
                    if nid:
                        # 레이어 닫기 시도
                        self._close_profile_layer()
                        return nid
                except Exception:
                    pass
                self._close_profile_layer()
                return ''

            # 3) 새 페이지/탭에서 span.user_id 추출
            time.sleep(1)

            # 새 탭이 열렸을 수 있음
            windows = self.driver.window_handles
            if len(windows) > 1:
                current = self.driver.current_window_handle
                self.driver.switch_to.window(windows[-1])
                time.sleep(2)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                nid = self._find_user_id_in_soup(soup)
                self.driver.close()
                self.driver.switch_to.window(current)
                time.sleep(1)
                return nid
            else:
                # 같은 페이지에서 로드됨
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                nid = self._find_user_id_in_soup(soup)
                if nid:
                    self.driver.back()
                    time.sleep(2)
                    return nid

            return ''
        except Exception:
            return ''

    def _close_profile_layer(self):
        """프로필 레이어 팝업 닫기"""
        try:
            # ESC 키로 닫기
            from selenium.webdriver.common.keys import Keys
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except Exception:
            pass

    @staticmethod
    def _find_user_id_in_soup(soup):
        """span.user_id 등에서 네이버 ID 추출"""
        for sel in ['span.user_id', 'span[class="user_id"]',
                    '.userid', '.member_id', '[class*="user_id"]']:
            elem = soup.select_one(sel)
            if elem:
                nid = elem.get_text(strip=True).strip('()').strip()
                if nid:
                    return nid
        return ''

    @staticmethod
    def _parse_article_date(date_str, ref_year):
        date_str = date_str.strip().rstrip('.')
        match = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', date_str)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
        match = re.match(r'^(\d{1,2})[.\-/](\d{1,2})$', date_str)
        if match:
            return ref_year, int(match.group(1)), int(match.group(2))
        match = re.match(r'^(\d{1,2}):(\d{2})$', date_str)
        if match:
            today = datetime.date.today()
            return today.year, today.month, today.day
        return 0, 0, 0

    # ──────────────────────────────────────────────
    # 회원 목록 스크래핑
    # ──────────────────────────────────────────────

    def scrape_members(self):
        if not self.club_id:
            self._status("clubid가 없습니다.")
            return []
        admin_url = f"{CAFE_BASE_URL}/ManageWholeMember.nhn?clubid={self.club_id}"
        self._status("회원 관리 페이지로 이동...")
        self.driver.get(admin_url)
        time.sleep(3)
        self._try_switch_to_cafe_frame()
        time.sleep(2)

        # id="_sortPerPage"로 100명 정렬
        try:
            elem = self.driver.find_element(By.ID, '_sortPerPage')
            select = Select(elem)
            select.select_by_value('100')
            self._status("페이지당 100명 표시로 설정")
            time.sleep(3)
            self._try_switch_to_cafe_frame()
            time.sleep(2)
        except Exception:
            self._status("_sortPerPage를 찾지 못함 — 기본값 사용")
            self._set_page_size_fallback()

        all_members = []
        seen_ids = set()
        page = 1
        empty_pages = 0

        while True:
            self._status(f"{page}페이지 스크래핑 중... (누적: {len(all_members)}명)")
            if page > 1:
                self._try_switch_to_cafe_frame()
                time.sleep(1)
            members = self._parse_current_page()
            if not members:
                empty_pages += 1
                if empty_pages >= 2:
                    break
                time.sleep(3)
                continue
            empty_pages = 0
            new_members = [m for m in members
                           if m.get('naver_id', '') and m['naver_id'] not in seen_ids]
            for m in new_members:
                seen_ids.add(m['naver_id'])
            if not new_members and page > 1:
                break
            all_members.extend(new_members)
            self._status(f"{page}p: {len(new_members)}명 (누적: {len(all_members)}명)")
            if not self._go_to_next_page(page):
                break
            page += 1
            time.sleep(2)

        self._status(f"회원 스크래핑 완료! 총 {len(all_members)}명")
        return all_members

    def _try_switch_to_cafe_frame(self):
        try:
            self.driver.switch_to.default_content()
            for name in ['cafe_main', 'cafe_manage']:
                try:
                    frame = self.driver.find_element(By.NAME, name)
                    self.driver.switch_to.frame(frame)
                    return True
                except NoSuchElementException:
                    continue
            try:
                frame = self.driver.find_element(By.ID, 'cafe_main')
                self.driver.switch_to.frame(frame)
                return True
            except NoSuchElementException:
                pass
            return False
        except Exception:
            return False

    def _set_page_size_fallback(self):
        """_sortPerPage를 못 찾았을 때 폴백"""
        try:
            for sel in ["select[name='perPage']", "select[name='countPerPage']",
                        "select.list_count", "select.count"]:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    select = Select(elem)
                    options = [o.get_attribute('value') for o in select.options]
                    max_val = max(options, key=lambda x: int(x) if x.isdigit() else 0)
                    select.select_by_value(max_val)
                    self._status(f"페이지당 {max_val}명 표시 (폴백)")
                    time.sleep(3)
                    return
                except Exception:
                    continue
        except Exception:
            pass

    def _parse_current_page(self):
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        members = []
        post_col_idx = -1
        tables = soup.find_all('table')
        target_table = None

        for table in tables:
            for row in table.find_all('tr'):
                headers = row.find_all(['th', 'td'])
                header_texts = [h.get_text(strip=True) for h in headers]
                joined = ''.join(header_texts)
                if sum(1 for kw in ['별명', '아이디', '등급', '게시글', '방문'] if kw in joined) >= 2:
                    for idx, txt in enumerate(header_texts):
                        if '게시글' in txt and '방문' not in txt:
                            post_col_idx = idx
                            break
                    target_table = table
                    break
            if target_table:
                break

        if target_table:
            for row in target_table.find_all('tr'):
                member = self._extract_from_row(row, post_col_idx)
                if member:
                    members.append(member)
            if members:
                return members

        for table in tables:
            for row in table.find_all('tr'):
                member = self._extract_from_row(row, -1)
                if member:
                    members.append(member)
            if members:
                return members
        return members

    def _extract_from_row(self, row, post_col_idx=-1):
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None
        row_text = row.get_text(strip=True)
        if sum(1 for kw in ['별명', '아이디', '등급명', '가입일', '게시글'] if kw in row_text) >= 2:
            return None

        naver_id = ''
        nickname = ''
        post_count = 0

        mid_elem = row.find(attrs={"memberid": True})
        if mid_elem:
            naver_id = mid_elem.get('memberid', '').strip()
        if not naver_id:
            for link in row.find_all('a', href=True):
                m = re.search(r'memberid=([^&"\']+)', link.get('href', ''))
                if m:
                    naver_id = m.group(1).strip()
                    break
        if not naver_id:
            return None

        for cell in cells:
            if cell.find('input', {'type': 'checkbox'}):
                continue
            for link in cell.find_all('a'):
                lt = link.get_text(strip=True)
                href = link.get('href', '')
                if ('memberid' in href or 'MemberInfo' in href) and lt and lt != naver_id:
                    nickname = lt
                    break
                if lt and not lt.isdigit() and lt != naver_id and not nickname:
                    nickname = lt
            if nickname:
                break

        if not nickname:
            for cell in cells:
                if cell.find('input', {'type': 'checkbox'}):
                    continue
                ct = cell.get_text(strip=True)
                if not ct or ct.isdigit() or re.match(r'^\d{4}[.\-/]', ct) or ct == naver_id:
                    continue
                nickname = ct
                break

        if 0 <= post_col_idx < len(cells):
            ct = cells[post_col_idx].get_text(strip=True)
            if ct.isdigit():
                post_count = int(ct)
        else:
            for cell in cells:
                ct = cell.get_text(strip=True)
                if ct.isdigit() and int(ct) < 1000000:
                    post_count = int(ct)
                    break

        nickname = self._clean_nickname(nickname or naver_id, naver_id)
        return {'naver_id': naver_id, 'nickname': nickname, 'post_count': post_count}

    @staticmethod
    def _clean_nickname(nickname, naver_id):
        if not nickname:
            return naver_id or ''
        if naver_id:
            nickname = re.sub(r'\s*[\(\[]\s*' + re.escape(naver_id) + r'\s*[\)\]]\s*',
                              '', nickname).strip()
        return nickname.strip() or naver_id or ''

    def _go_to_next_page(self, current_page):
        try:
            self.driver.switch_to.default_content()
            self._try_switch_to_cafe_frame()
            next_page = current_page + 1

            for sel in [".paginate a", ".pagination a", ".page_area a",
                        ".paging a", "[class*='page'] a"]:
                try:
                    for link in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if link.text.strip() == str(next_page) and link.is_displayed():
                            link.click()
                            time.sleep(2)
                            return True
                except Exception:
                    continue

            for link in self.driver.find_elements(By.TAG_NAME, "a"):
                try:
                    if link.text.strip() == str(next_page) and link.is_displayed():
                        if link.get_attribute('href') or link.get_attribute('onclick'):
                            link.click()
                            time.sleep(2)
                            return True
                except Exception:
                    continue

            try:
                self.driver.execute_script(f"goPage({next_page})")
                time.sleep(2)
                return True
            except Exception:
                pass

            for sel in ["a.pgR", "a.next", "a[class*='next']"]:
                try:
                    for link in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if link.is_displayed():
                            link.click()
                            time.sleep(2)
                            return True
                except Exception:
                    continue

            return False
        except Exception:
            return False

    # ──────────────────────────────────────────────
    # 저장 / 실행
    # ──────────────────────────────────────────────

    def save_json(self, members, output_path, **extra):
        payload = {
            'source': 'naver_cafe_admin',
            'cafe_name': self.cafe_name,
            'exported_at': datetime.datetime.now().isoformat(),
            'members': members
        }
        for key, val in extra.items():
            if val and isinstance(val, (dict, str)):
                payload[key] = val
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self._status(f"JSON 저장: {output_path}")

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def run_full(self, output_path, mode='members', start_date=None, end_date=None, board_config=None):
        """
        mode='members': 회원 조회만
        mode='boards': 게시판 집계만 (기존 회원 데이터 기반)
        mode='all': 회원 + 게시판
        board_config: {'club_id': '...', 'boards': {'출석체크': '51', ...}}
        """
        try:
            self.start()
            self.open_login_page()
            if not self.wait_for_login():
                self._status("로그인에 실패했습니다.")
                return []

            club_id = board_config.get('club_id') if board_config else None
            if not self.get_club_id(club_id):
                self._status("카페 ID를 찾지 못했습니다.")
                return []

            members = []

            # ── 회원 조회 ──
            if mode in ('members', 'all'):
                members = self.scrape_members()
                if members:
                    self.save_json(members, output_path)

            # ── 게시판 집계 ──
            if mode in ('boards', 'all') and start_date and board_config:
                # 기존 회원 데이터 로드 (boards 모드일 때)
                if not members and os.path.exists(output_path):
                    with open(output_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                    members = existing.get('members', [])

                if not members:
                    self._status("회원 데이터가 없습니다. 먼저 회원 조회를 하세요.")
                    return []

                # 닉네임 → ID 매핑 + ID set (폴백 매칭 확인용)
                nickname_to_id = {}
                id_set = set()
                for m in members:
                    nick = m.get('nickname', '').strip()
                    nid = m.get('naver_id', '').strip()
                    if nick and nid:
                        nickname_to_id[nick] = nid
                    if nid:
                        id_set.add(nid)

                boards = board_config.get('boards', {})
                attendance_data = {}
                weekly_review_data = {}
                lastone_review_data = {}
                supplement_data = {}
                live_review_data = {}

                # 1) 출석체크
                mid = boards.get('출석체크')
                if mid:
                    result = self.scrape_board_posts(
                        mid, start_date, end_date, nickname_to_id, id_set, "출석체크")
                    if isinstance(result, dict):
                        attendance_data = result

                # 2) 수강생 주차별 후기
                mid = boards.get('수강생 주차별 후기')
                if mid:
                    result = self.scrape_board_posts(
                        mid, start_date, end_date, nickname_to_id, id_set, "주차별 후기")
                    if isinstance(result, dict):
                        weekly_review_data = result

                # 3) 라스트원 강의후기
                mid = boards.get('라스트원 강의후기')
                if mid:
                    result = self.scrape_board_posts(
                        mid, start_date, end_date, nickname_to_id, id_set, "라스트원 후기")
                    if isinstance(result, dict):
                        lastone_review_data = result

                # 4) 졸업생 보충강의 후기
                mid = boards.get('졸업생 보충강의 후기')
                if mid:
                    result = self.scrape_board_posts(
                        mid, start_date, end_date, nickname_to_id, id_set, "보충강의 후기")
                    if isinstance(result, dict):
                        supplement_data = result

                # 5) 졸업생 라이브 후기
                mid = boards.get('졸업생 라이브 후기')
                if mid:
                    result = self.scrape_board_posts(
                        mid, start_date, end_date, nickname_to_id, id_set, "라이브 후기")
                    if isinstance(result, dict):
                        live_review_data = result

                self.save_json(members, output_path,
                               attendance_data=attendance_data,
                               attendance_start_date=start_date,
                               weekly_review_data=weekly_review_data,
                               lastone_review_data=lastone_review_data,
                               supplement_data=supplement_data,
                               live_review_data=live_review_data)

            return members
        except Exception as e:
            self._status(f"오류 발생: {e}")
            return []
        finally:
            self.close()


if __name__ == '__main__':
    import sys
    cafe = sys.argv[1] if len(sys.argv) > 1 else 'lastone0228'
    sd = sys.argv[2] if len(sys.argv) > 2 else None
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cafe_members.json')
    config = {"club_id": "31136700", "boards": {"출석체크": "51"}}
    s = CafeScraper(cafe)
    s.run_full(out, mode='all' if sd else 'members', start_date=sd, board_config=config)
