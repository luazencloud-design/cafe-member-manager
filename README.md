# Naver Cafe Member Manager

Naver Cafe member data manager with Selenium scraping, multi-column sorting, filtering, and CSV/XLSX import.

## Requirements

- Python 3.10+
- Google Chrome (for Selenium scraping)

## Setup

```bash
cd cafe-member-manager

# Create virtual environment
uv venv .venv --python 3.14  # or: python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install selenium beautifulsoup4 openpyxl
```

## Quick Start

```bash
# Run the app
.venv/Scripts/pythonw.exe sortable_table.py

# Or double-click:
카페회원관리.bat
```

## Project Structure

```
cafe-member-manager/
├── sortable_table.py      # Main GUI app (Tkinter)
├── cafe_scraper.py        # Selenium scraper module
├── board_config.json      # Board menu IDs & cafe settings
├── column_config.json     # CSV column keyword mappings
├── member_data.json       # Auto-saved member data (runtime)
├── cafe_members.json      # Scraper output (runtime)
├── 카페회원관리.bat         # Windows launcher
├── test_*.csv/json        # Test data files
└── .venv/                 # Virtual environment
```

## Architecture

### sortable_table.py (GUI)

Tkinter-based table with 10 fixed columns:

| # | Column | Type | Source |
|---|--------|------|--------|
| 0 | 네이버ID | text | Scraper (member admin) |
| 1 | 카페닉네임 | text | Scraper (member admin) |
| 2 | 본명 | text | CSV import |
| 3 | 동행천만 | bool | CSV import (★ if 소속 contains 기) |
| 4 | 밥상모임 | bool | CSV import |
| 5 | 게시글수 | number | Scraper (member admin) |
| 6 | 출석체크 | number | Scraper (board: 출석체크/인사) |
| 7 | 수강생 후기(주차별/라스트원) | composite | Scraper (2 boards combined: "합계(A/B)") |
| 8 | 보충강의 | number | Scraper (board: 졸업생 보충강의 후기) |
| 9 | 라이브 후기 | bool | Scraper (board: 졸업생 라이브 후기, ◇ mark) |

### cafe_scraper.py (Scraper)

Selenium-based scraper with two modes:

- **`mode='members'`** : Scrape member list from cafe admin page (`ManageWholeMember.nhn`)
- **`mode='boards'`** : Scrape 5 boards for attendance/review counts

Board URL format:
```
https://cafe.naver.com/f-e/cafes/{club_id}/menus/{menu_id}?page=N&size=50
```

## Features

### Multi-Column Sorting
- Click header: cycle sort direction (↕ → ↓ → ↑ → remove)
- Click another header: adds secondary sort (Python stable sort)
- Header displays: `게시글수 ↓` `출석체크 ↑`
- "정렬 초기화" button resets all

### Filter Mode
Filter bar below table with per-column buttons. Click to cycle:

| Mode | Meaning | Color |
|------|---------|-------|
| `=` | Show all (default) | Gray |
| `∩` | Has value — intersection (ALL must have) | Blue |
| `∪` | Has value — union (ANY can have) | Green |
| `!∩` | No value — intersection (ALL must be empty) | Red |
| `!∪` | No value — union (ANY can be empty) | Orange |

Empty values: `""`, `"0"`, `"0(0/0)"`, `"X"`

### Cell Editing
- Double-click any cell in columns 0-4 (네이버ID ~ 밥상모임) to edit
- Columns 5-9 (게시글수 ~ 라이브후기) are read-only (managed by scraper)
- Enter = confirm, Escape = cancel

### Column Reordering
- Right-click header → "왼쪽/오른쪽으로 이동"

### CSV/XLSX Import

**속성 매핑** toolbar buttons:
- **동행천만 CSV** : Matches by 네이버ID/카페닉네임/본명, checks 소속 column for "기" → ★
- **밥상모임 CSV** : Matches and fills value from matching column
- **본명 CSV** : Matches and fills 본명 (removes parenthetical content like "송호상(토)" → "송호상")

**Column detection priority:**
1. Exact match from `column_config.json` keywords
2. Case-insensitive match
3. Auto-pattern (id, 닉네임, 본명, etc.)
4. Data-based inference (Korean 2-4 chars = name, alphanumeric 4-30 chars = ID, etc.)

**Nickname matching priority:**
1. Exact match
2. Case-insensitive (no homonyms)
3. Space-insensitive (no homonyms): "이번이 마지막" = "이번이마지막"

**"닉네임 (id)" format parsing:**
```
"준준성수 (tntnkj)" → nick=준준성수, id=tntnkj
"spoon0 (트레이서)" → nick=트레이서, id=spoon0
"ryujs37767(다닝)"  → nick=다닝, id=ryujs37767
```

### Scraper Features

**Member scraping:**
- Uses `id="_sortPerPage"` select element to set 100 per page
- Header row analysis to find correct "게시글" column (not "방문수")
- Cleans nicknames: removes "(naver_id)" suffix, no duplicate removal

**Board scraping:**
- Nickname matching via `span.nickname` in article list → direct count (no page entry needed)
- Fallback: click author → "게시글 보기" button → read `span.user_id` → verify against member ID set
- Date range: start_date to end_date (inclusive)
- Fast-forward: if range is >1 month old, uses `button.btn.type_next` to skip 10 pages at a time, then backtracks for precision

**Board scraping resets** 출석체크, 수강생후기, 보충강의, 라이브후기 columns to zero before each run.

## Configuration Files

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

Editable via "게시판 변수 설정" button in the app.

### column_config.json

```json
{
  "id_keywords": "네이버ID,네이버id,naver_id,ID,id,아이디,Id,iD",
  "nick_keywords": "카페닉네임,닉네임,별명,nickname",
  "name_keywords": "본명,이름,성명,성함,실명,활동명,name"
}
```

Editable via "열 이름 설정" button. Used by CSV/XLSX import to find matching columns.

## Data Flow

```
┌─────────────┐     ┌──────────────────┐
│  회원 조회    │────>│ cafe_members.json │
│ (Selenium)   │     │  members: [...]   │
└─────────────┘     └────────┬─────────┘
                             │
┌─────────────┐              │    ┌──────────────────┐
│ 게시판 집계   │──────────────┘───>│ cafe_members.json │
│ (Selenium)   │                   │  + attendance_data │
└─────────────┘                   │  + weekly_review   │
                                  │  + lastone_review  │
                                  │  + supplement_data │
                                  │  + live_review     │
        ┌─────────────────────────┘
        │
        v
┌───────────────┐     ┌──────────────────┐
│ _merge_cafe_  │────>│ member_data.json  │
│ json()        │     │ (auto-saved)      │
└───────────────┘     └──────────────────┘
        │
        v
┌───────────────┐
│  Tkinter GUI  │<──── CSV/XLSX import (본명, 동행천만, 밥상모임)
│  (table view) │────> CSV export (with filter applied)
└───────────────┘
```

## Key Classes

### `SortableTable` (sortable_table.py)
- `_build_ui()` : Toolbar, table, filter bar, status bar
- `_on_header_click(column)` : Multi-column sort
- `_cycle_filter(col)` / `_set_filter_mode(col, mode)` : Filter toggle
- `_passes_filter(row)` : Row visibility check
- `_merge_cafe_json(payload)` : Merge scraper data into table
- `_match_csv_to_rows(csv_path)` : CSV matching with fallback chain
- `_split_nick_id(value)` : Parse "nick (id)" format bidirectionally
- `_infer_headers(raw_rows)` : Auto-detect columns in headerless CSVs
- `_find_csv_key(keys, config_key, csv_rows)` : 4-stage column detection

### `CafeScraper` (cafe_scraper.py)
- `scrape_members()` : Member list from admin page
- `scrape_board_posts(menu_id, start, end, nick_map, id_set, label)` : Board article counting
- `_extract_article_rows(soup)` : Parse article list HTML (span.nickname, date, URLs)
- `_get_user_id_via_profile(nickname)` : Fallback ID lookup via author profile click
- `_click_skip_button()` : Fast-forward 10 pages via button.btn.type_next
- `run_full(output, mode, start_date, end_date, board_config)` : Orchestrator

## CLI Usage

```bash
# Member scraping only
python cafe_scraper.py lastone0228

# With board scraping
python cafe_scraper.py lastone0228 2026-03-14
```

## License

Internal tool. Not for public distribution.
