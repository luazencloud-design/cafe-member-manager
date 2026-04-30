# 📊 Naver Cafe Member Manager (cafe-member-manager)

> **네이버 카페 회원 관리 데스크톱 앱 — Selenium 스크래핑 + 다중 정렬·필터·CSV/XLSX 매핑**
> 회원 목록 + 5개 게시판 활동을 자동 수집하고 Tkinter GUI에서 한눈에 관리합니다.

- **GitHub:** [luazencloud-design/cafe-member-manager](https://github.com/luazencloud-design/cafe-member-manager) *(또는 TriplePistol/pagecraft 모노레포)*
- **기술 스택:** Python 3.10+ · Tkinter (ttk.Treeview) · Selenium 4 · BeautifulSoup4 · openpyxl
- **타깃 카페:** lastone0228 (board_config.json에서 변경 가능)

---

## 📋 목차

1. [프로젝트 개요](#-프로젝트-개요)
2. [파일 구성](#-파일-구성)
3. [10개 고정 컬럼](#-10개-고정-컬럼)
4. [코드 원리 — 데이터 흐름](#-코드-원리--데이터-흐름)
5. [정렬·필터·검색](#-정렬필터검색)
6. [CSV/XLSX 매핑 (4단계 폴백)](#-csvxlsx-매핑-4단계-폴백)
7. [다운로드 방법](#-다운로드-방법)
8. [설치 (setup.bat)](#-설치-setupbat)
9. [실행 방법](#-실행-방법)
10. [설정 파일](#-설정-파일)
11. [트러블슈팅](#-트러블슈팅)
12. [후임자 메모](#-후임자-메모)

---

## 🎯 프로젝트 개요

**핵심 기능:**
1. **회원 목록 스크래핑** — 네이버 카페 관리 페이지(`ManageWholeMember.nhn`)에서 회원 ID/닉네임/게시글수 추출
2. **게시판 활동 집계** — 5개 게시판(출석체크/주차별후기/라스트원후기/보충강의/라이브후기) 일괄 수집
3. **다중 정렬** — 헤더 클릭으로 ASC/DESC 추가, Python stable sort
4. **필터** — Ctrl+헤더 클릭, 5가지 모드 순환 (= → ∩ → ∪ → !∩ → !∪)
5. **CSV/XLSX 속성 매핑** — 동행천만/밥상모임/본명 정보 자동 병합 (4단계 컬럼 매칭 폴백)
6. **셀 편집** — 더블클릭으로 직접 수정 (컬럼 0~4만)
7. **자동 저장** — `member_data.json` 자동 보존

---

## 📁 파일 구성

```
cafe-member-manager/
├── sortable_table.py        ⭐ Tkinter GUI + 데이터 관리 (~2,050줄)
│                             - SortableTable 클래스
│                             - 멀티 정렬 / 필터 / 검색 / 셀 편집
│                             - CSV/XLSX 속성 매핑
├── cafe_scraper.py          ⭐ Selenium 스크래핑 엔진 (~1,062줄)
│                             - CafeScraper 클래스
│                             - mode='members': 회원 관리 페이지
│                             - mode='boards': 5개 게시판 일괄 집계
│                             - Fast-Forward (1개월 이상 과거 시 10페이지 점프)
│                             - Fallback ID lookup (프로필 클릭 → user_id)
├── board_config.json        카페명 / 클럽ID / 게시판 메뉴 ID 매핑
├── column_config.json       CSV 열 이름 키워드 매핑 (ID/닉네임/본명)
├── requirements.txt         selenium >=4.0 / beautifulsoup4 / openpyxl
├── setup.bat                Python 설치 확인 + .venv 생성 + 의존성 설치
├── 카페회원관리.bat          앱 실행 (.venv 없으면 setup.bat 자동 실행)
├── member_data.json         🔄 런타임 자동 저장 (이전 세션 데이터 복원)
├── cafe_members.json        🔄 스크래퍼 출력 (members + 게시판 집계)
└── README.md                이 문서
```

---

## 🗂 10개 고정 컬럼

| # | 컬럼 | 타입 | 출처 | 편집 가능 |
|---|------|------|------|-----------|
| 0 | 네이버ID | text | 스크래퍼 (회원관리) | ✅ |
| 1 | 카페닉네임 | text | 스크래퍼 (회원관리) | ✅ |
| 2 | 본명 | text | CSV import | ✅ |
| 3 | 동행천만 | bool (★/X) | CSV import (소속에 '기' 포함) | ✅ |
| 4 | 밥상모임 | bool (O/X) | CSV import | ✅ |
| 5 | 게시글수 | number | 스크래퍼 (회원관리) | ❌ 읽기전용 |
| 6 | 출석체크 | number | 스크래퍼 (게시판 51) | ❌ |
| 7 | 수강생 후기(주차별/라스트원) | composite "합계(A/B)" | 스크래퍼 (게시판 105+22) | ❌ |
| 8 | 보충강의 | number | 스크래퍼 (게시판 79) | ❌ |
| 9 | 라이브 후기 | bool (◇) | 스크래퍼 (게시판 110) | ❌ |

---

## 🧬 코드 원리 — 데이터 흐름

```
[1] 카페회원관리.bat 더블클릭
     ↓
[2] sortable_table.py 시작
     - board_config.json 로드
     - column_config.json 로드
     - member_data.json 복원 (이전 세션)
     - Tkinter UI 빌드 (툴바 / Treeview / 필터버튼 / 상태바)

[3a] "회원 조회" 버튼 클릭 → 별도 스레드에서 CafeScraper 실행
     - Chrome 시작 (봇 감지 우회)
     - 네이버 로그인 페이지 → 사용자 수동 로그인 대기 (최대 5분)
     - club_id 설정 (config 우선)
     - mode='members':
         - id="_sortPerPage"로 100명/페이지 설정
         - 페이지 순회, 각 행에서 (memberid 속성 또는 href에서 추출)
         - 닉네임 정리 (suffix "(naver_id)" 제거)
         - 게시글수 추출
         - 빈 페이지 2회 연속 시 종료
     - cafe_members.json에 저장
     ↓
     _on_scrape_complete() → _merge_cafe_json()
     - 신규/갱신 회원 row_flags 표시 (하이라이트)
     - 화면 갱신

[3b] "게시판 집계" 버튼 클릭 → 날짜 범위 입력 → 별도 스레드
     - mode='boards':
         - 닉네임 → ID 매핑 생성 (members 기반)
         - 5개 게시판별 scrape_board_posts(menu_id, range)
             1) Fast-Forward 단계 (1개월 이상 과거)
                - button.btn.type_next 클릭 (10페이지 점프)
                - 범위 초과하면 Backtrack (10페이지 되돌아가 1페이지씩)
             2) 정밀 탐색 (1페이지씩)
                - article 행에서 닉네임 → ID 직접 매칭
                - 실패 시 _get_user_id_via_profile (프로필 클릭 → user_id)
         - attendance_data, weekly_review_data, lastone_review_data,
           supplement_data, live_review_data 생성
     - cafe_members.json에 병합 저장

[4] CSV/XLSX 속성 매핑
     "동행천만 CSV" → '소속' 열에서 '기' 포함 여부 → '★' 표시
     "밥상모임 CSV" → 매칭 → 해당 열 값으로 '밥상모임' 채움
     "본명 CSV" → 키워드 기반 (폴백 금지) → '본명' 채움
     ↓
     _match_csv_to_rows() — 4단계 폴백 매칭 (아래 참고)

[5] 정렬 / 필터 / 검색
     - 헤더 클릭 → sort_order 추가/제거 (3단계: ASC→DESC→제거)
     - Ctrl+헤더 클릭 → filter_modes 5단계 순환
     - 검색창 입력 → 자동완성 팝업 (startswith 우선)
     - 더블클릭 → 셀 편집 (Entry 위젯)

[6] CSV 내보내기
     "CSV로 저장" → 화면에 보이는 행만 (필터 적용)
                   → utf-8-sig 인코딩 (한글 Excel 호환)
```

---

## 🔍 정렬·필터·검색

### 다중 정렬 (헤더 클릭)

```
1번째 헤더 클릭 → ASC ↑ 추가
같은 헤더 다시 클릭 → DESC ↓ 변경
또 같은 헤더 클릭 → 제거
다른 헤더 클릭 → 부차 정렬 추가 (Python stable sort)

표시: "게시글수 ↓" "출석체크 ↑" (동시 표시)
"정렬 초기화" 버튼으로 모두 제거
```

### 필터 모드 (Ctrl+헤더 클릭, 5단계 순환)

| 모드 | 의미 | 색상 | 예 |
|------|------|------|-----|
| `=` | 전체 표시 (기본) | 회색 | - |
| `∩` | 모두 있음 (AND) | 파랑 | 동행천만∩ + 밥상모임∩ = 둘 다 가진 회원 |
| `∪` | 하나라도 있음 (OR) | 초록 | 동행천만∪ + 밥상모임∪ = 둘 중 하나만이라도 |
| `!∩` | 모두 없음 (AND) | 빨강 | 동행천만!∩ = 동행천만 없는 회원 |
| `!∪` | 하나라도 없음 (OR) | 주황 | 동행천만!∪ = 동행천만 없는 회원 (개별) |

**"값" 정의:** `''`, `'0'`, `'0(0/0)'`, `'X'` 는 모두 "값 없음".

### 검색 + 자동완성

- 검색 대상 선택: 전체 / ID / 닉네임 / 본명
- 입력 중 팝업 갱신 (startswith 우선, contains 후순위)
- 결과 클릭 → 행으로 스크롤 + 선택

---

## 📋 CSV/XLSX 매핑 (4단계 폴백)

`_find_csv_key(csv_keys, config_key, csv_rows)` — CSV의 어느 열이 ID/닉네임/본명에 해당하는지 결정.

### 단계 1: 정규화 매칭 (공백/대소문자 무시)

```python
'네이버ID' ↔ '네이버 id', 'NAVER_ID' ↔ 'naver_id' 모두 매칭
column_config.json 의 키워드 사용
```

### 단계 2: 자동 패턴

```python
id_keywords  : 'id' 포함 또는 '아이디' 포함
nick_keywords: '닉네임'/'별명'/'nickname' 포함
name_keywords: '본명'/'이름'/'성명'/'성함'/'실명'/'활동명' 포함
```

### 단계 3: 데이터 기반 신뢰도 점수 (임계값 0.5)

```python
name_keywords: 순수 한글 2-4자 비율 × (표준편차 ≤ 1.0)
id_keywords:   영숫자 4-30자 비율
nick_keywords: 한글 포함 평균 3+ 비율
```

### 단계 4: 폴백 (조건부)

- ID/닉네임 열이 완전히 없을 때만 폴백
- 본명 열이 없으면 폴백 안 함 (잘못된 매칭 방지) ⭐ 변경 3
- 폴백 시 모든 열을 순회하며 패턴 탐색

### 닉네임 분리 (양방향 지원)

```
"준준성수 (tntnkj)"   → nick="준준성수", id="tntnkj"
"spoon0 (트레이서)"   → nick="트레이서", id="spoon0"
"ryujs37767(다닝)"   → nick="다닝", id="ryujs37767"
```

ID 규칙: `[a-zA-Z0-9._-]+` 만 인정.

### 행 매칭 우선순위

```
1) ID 열 정확 매칭
2) 닉네임 열:
   a. 정확 매칭
   b. 대소문자 무시 (동음이인 없을 때만)
   c. 띄어쓰기+대소문자 무시 (동음이인 없을 때만)
   d. 분리된 ID 부분으로 재시도
3) 본명 열 정확 매칭 (폴백 금지)
```

### 이름 스마트 추출

```
"박찬수.바보"     → "박찬수"  (3자 한글 1.0점)
"이승훈/그냥미친놈" → "이승훈"
"로켓덕후 이동현"   → "이동현"
"송호상(토)"       → "송호상"  (괄호 제거)

3자 한글 = 1.0점, 2/4자 한글 = 0.7점
```

---

## 📥 다운로드 방법

```bash
git clone https://github.com/luazencloud-design/cafe-member-manager.git
cd cafe-member-manager
```

또는 **Code → Download ZIP**.

---

## 🛠 설치 (setup.bat)

### 사전 요구

- **Python 3.10+** ([python.org](https://python.org)에서 설치, "Add to PATH" 체크)
- **Google Chrome** (Selenium 스크래핑용)

### 자동 설치 (권장)

`setup.bat` 더블클릭 → 자동으로:
1. Python 3.10+ 확인
2. Chrome 설치 확인 (경고만)
3. `.venv` 가상환경 생성
4. `pip install selenium beautifulsoup4 openpyxl`
5. 완료 메시지

### 수동 설치

```bash
cd cafe-member-manager

# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## ▶ 실행 방법

### 방법 A — 더블클릭 ⭐

`카페회원관리.bat` 더블클릭. `.venv` 없으면 자동으로 setup 실행.

### 방법 B — 명령줄

```bash
.venv/Scripts/pythonw.exe sortable_table.py    # Windows
./.venv/bin/python sortable_table.py           # macOS/Linux
```

### 방법 C — CLI 직접 (스크래퍼만)

```bash
# 회원만 스크래핑
python cafe_scraper.py lastone0228

# 회원 + 게시판 집계 (날짜 범위)
python cafe_scraper.py lastone0228 2026-03-14
```

---

## ⚙ 설정 파일

### board_config.json

```json
{
  "cafe_name": "lastone0228",
  "club_id": "31136700",
  "boards": {
    "출석체크": "51",
    "수강생 주차별 후기": "105",
    "라스트원 강의후기": "22",
    "졸업생 보충강의 후기": "79",
    "졸업생 라이브 후기": "110"
  }
}
```

> 다른 카페로 바꾸려면 `cafe_name`과 `club_id`, 게시판 menu_id를 변경하거나 GUI의 "게시판 변수 설정" 버튼 사용.

### column_config.json

```json
{
  "id_keywords": "네이버ID,네이버id,naver_id,ID,id,아이디,Id,iD",
  "nick_keywords": "카페닉네임,닉네임,별명,nickname",
  "name_keywords": "본명,이름,성명,성함,실명,활동명,name"
}
```

> GUI의 "열 이름 설정" 버튼으로도 편집 가능.

### member_data.json (자동 저장)

```json
{
  "saved_at": "2026-04-30T15:30:45.123456",
  "members": [
    ["naver_id_1", "닉네임1", "본명1", "★", "O", "42", "5", "10(5/5)", "2", ""],
    ...
  ]
}
```

타입별 기본값 패딩 (로드 시):
- `SORT_TYPE_NUMBER` → `'0'`
- `SORT_TYPE_COMPOSITE` → `'0(0/0)'`
- 나머지 → `''`

### cafe_members.json (스크래퍼 출력 + 게시판 병합)

```json
{
  "source": "naver_cafe_admin",
  "cafe_name": "lastone0228",
  "exported_at": "...",
  "members": [{ "naver_id": "...", "nickname": "...", "post_count": 42 }, ...],
  "attendance_data": { "id1": 5, ... },
  "weekly_review_data": { "id1": 10, ... },
  "lastone_review_data": { "id1": 5, ... },
  "supplement_data": { "id1": 2, ... },
  "live_review_data": { "id1": 1, ... }
}
```

---

## 🛠 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| Chrome 시작 안 됨 | Chrome 설치 확인. ChromeDriver는 Selenium 4가 자동 관리 |
| 로그인 후 진행 안 됨 | `wait_for_login` 5분 타임아웃. URL/NID_AUT 쿠키 확인 |
| 닉네임이 잘못 매칭됨 | 닉네임 분리 규칙 확인 (`_split_nick_id`). ID 패턴은 `[a-zA-Z0-9._-]+` 만 |
| CSV 매핑이 잘못됨 | `column_config.json`의 키워드 추가 또는 GUI "열 이름 설정"에서 편집 |
| 게시판 집계가 빠짐 | board_config.json의 menu_id 정확한지 확인 |
| 본명 컬럼이 비어있음 | CSV에 본명 키워드 열이 없음. 폴백이 의도적으로 비활성화됨 |
| Fast-Forward가 안 됨 | `button.btn.type_next` selector 확인 (네이버 UI 변경 가능) |
| Treeview 깜빡임 | 데이터 1만 건 이상 시 발생. 페이지네이션 미구현 (현재 한계) |

---

## 📝 후임자 메모

### 자주 변경하는 곳

| 변경 항목 | 위치 |
|----------|------|
| 카페 / 클럽ID / 게시판 | `board_config.json` 또는 GUI "게시판 변수 설정" |
| CSV 열 키워드 | `column_config.json` 또는 GUI "열 이름 설정" |
| 컬럼 추가/삭제 | `sortable_table.py` `FIXED_COLUMNS` (10개 고정 — 변경 시 widespread 영향) |
| 필터 모드 | `sortable_table.py` `FILTER_CYCLE` 배열 |
| 본명 추출 점수 함수 | `_score_column()` (한글 2-4자, 표준편차 등) |
| 닉네임 분리 정규식 | `_split_nick_id()` (괄호/공백 처리) |
| 게시판 HTML selector | `cafe_scraper.py` `_extract_article_rows()` 폴백 셀렉터 배열 |
| 회원 행 selector | `cafe_scraper.py` `_parse_current_page()` 헤더 행 탐색 |
| Fast-Forward 임계 | `(today - end_date).days > 30` (30일 이상 과거) |

### 보안 / 자동화 우회

```python
# cafe_scraper.py
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
self.driver.execute_cdp_cmd(
  "Page.addScriptToEvaluateOnNewDocument",
  {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
)
```

> 자동 로그인은 의도적으로 미구현 (보안). 사용자가 매번 직접 로그인.

### 알려진 제약

1. **HWP 미지원** — 카페 스크래핑과는 별도, 회원 정보만 (kakao-bot에서 HWP 처리)
2. **이중 클릭 편집은 컬럼 0~4만** — 스크래퍼 관리 컬럼(5~9)은 읽기전용
3. **데이터 1만 건 이상 시 Treeview 깜빡임** — 가상화 미구현
4. **Selenium 4.0+ 의존** — Selenium Manager가 ChromeDriver 자동 관리

### 데이터 보호

- 모든 데이터는 로컬 JSON (클라우드 업로드 없음)
- `member_data.json`, `cafe_members.json`는 실행 디렉토리 내
- 자동 로그인 미구현 (네이버 보안 정책 준수)

### 인수인계 체크리스트

- [ ] Python 3.10+ 설치 확인
- [ ] Chrome 설치 확인
- [ ] `setup.bat` 또는 수동 환경 구성
- [ ] `board_config.json` 의 카페 정보 확인
- [ ] `column_config.json` 의 키워드 검토
- [ ] 앱 실행 → "회원 조회" → 로그인 → 데이터 확인
- [ ] CSV 임포트 테스트 (동행천만/밥상모임/본명)
- [ ] 게시판 집계 테스트 (작은 날짜 범위로 먼저)
- [ ] 정렬/필터/검색 동작 확인
- [ ] CSV 내보내기 확인

---

*Naver Cafe Member Manager — Python 3.10 · Tkinter · Selenium 4 · BeautifulSoup4*
