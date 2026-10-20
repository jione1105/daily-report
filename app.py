import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정 (와이드 레이아웃)
st.set_page_config(
    page_title="일일 및 주간 리포트 아카이브",
    page_icon="📈",
    layout="wide",
)

# [CSS 스타일] 사이드바 정렬 및 버튼 음영 커스텀
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2.0rem !important;
            padding-left: 2.0rem !important;
            padding-right: 2.0rem !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 2.0rem !important;
            padding-left: 2.0rem !important;
            padding-right: 2.0rem !important;
        }
        section[data-testid="stSidebar"] hr {
            margin-left: 0rem !important;
            margin-right: 0rem !important;
        }
        
        /* 현재 선택된 날짜 버튼 음영 (부드러운 파란색 계열) */
        div.stButton > button[kind="primary"] {
            background-color: #E2EBF5 !important;
            color: #1E3E62 !important;
            border: 1px solid #B0C4DE !important;
            font-weight: bold !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# 기준 폴더 경로
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_available_reports(directory, prefix="Daily_Report"):
  """특정 파일명 패턴을 가진 HTML 파일들을 스캔하여 날짜별 정렬"""
  reports = {}
  if not os.path.exists(directory):
    return reports

  for f in os.listdir(directory):
    if not f.lower().endswith(".html"):
      continue
    if prefix in f:
      match = re.search(r"(\d{4}-\d{2}-\d{2})", f)
      if match:
        date_str = match[1]
        reports[date_str] = os.path.join(directory, f)

  return dict(sorted(reports.items(), key=lambda x: x[0], reverse=True))


def parse_html_tables(file_path):
  """일일 HTML 파일 안의 테이블 데이터를 파싱하여 딕셔너리로 추출"""
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      soup = BeautifulSoup(f.read(), "html.parser")

    tables_data = {}
    tables = soup.find_all("table")
    for table in tables:
      rows = table.find_all("tr")
      if not rows:
        continue
      headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
      for row in rows[1:]:
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cols) == len(headers) and re.match(
            r"^\d{4}-\d{2}-\d{2}$", cols[0]
        ):
          date_val = cols[0]
          for i, h in enumerate(headers[1:], 1):
            if i < len(cols):
              try:
                val = float(cols[i].replace(",", ""))
                if h not in tables_data:
                  tables_data[h] = {}
                tables_data[h][date_val] = val
              except ValueError:
                pass
    return tables_data
  except Exception:
    return {}


def generate_weekly_reports(directory):
  """일일 리포트들을 월요일 기준으로 주차별 그룹화하여 주간 요약 파일 자동 생성"""
  daily_reports = get_available_reports(directory, prefix="Daily_Report")
  if not daily_reports:
    return

  # 날짜별 데이터 파싱 미리 수행
  daily_data_map = {}
  for d_str, f_path in daily_reports.items():
    daily_data_map[d_str] = parse_html_tables(f_path)

  sorted_dates = sorted(list(daily_reports.keys()))

  # 각 날짜별로 해당 주의 월요일 구하기
  # 월요일을 기준으로 주간 리포트 파일명 결정
  weeks_map = {}
  for d_str in sorted_dates:
    dt = datetime.strptime(d_str, "%Y-%m-%d")
    # 월요일 계산 (weekday: 월=0 ... 일=6)
    monday_dt = dt - timedelta(days=dt.weekday())
    monday_str = monday_dt.strftime("%Y-%m-%d")

    if monday_str not in weeks_map:
      weeks_map[monday_str] = []
    weeks_map[monday_str].append(d_str)

  # 모든 월요일에 대해, 직전 주(1주 전)와 그 전 주(2주 전) 데이터가 모두 확보된 경우 주간 파일 생성
  all_mondays = sorted(list(weeks_map.keys()))

  for i, current_monday in enumerate(all_mondays):
    # 직전 주(1주 전)의 월요일 계산
    prev_monday_dt = datetime.strptime(current_monday, "%Y-%m-%d") - timedelta(
        days=7
    )
    prev_monday_str = prev_monday_dt.strftime("%Y-%m-%d")

    # 1주 전 데이터와 2주 전 데이터를 모으기 위해 날짜 리스트 정렬 활용
    # 현 주차 월요일 이전의 날짜들 중 최근 10영업일을 1주 전(최근 5일)과 2주 전(그 이전 5일)으로 확정
    available_before = [d for d in sorted_dates if d < current_monday]
    if len(available_before) < 10:
      continue

    prev_1week_dates = available_before[-5:]  # 1주 전 (직전 5영업일)
    prev_2week_dates = available_before[-10:-5]  # 2주 전 (그 전 5영업일)

    weekly_filename = os.path.join(
        directory, f"Weekly_Report({current_monday}).html"
    )
    if os.path.exists(weekly_filename):
      continue

    # 데이터 집계 및 평균 계산
    all_metrics_data = {}
    for d_str in prev_2week_dates + prev_1week_dates:
      t_data = daily_data_map.get(d_str, {})
      for metric, d_map in t_data.items():
        if metric not in all_metrics_data:
          all_metrics_data[metric] = {}
        if d_str in d_map:
          all_metrics_data[metric][d_str] = d_map[d_str]

    target_metrics = [
        "Wheat",
        "Corn",
        "Soybean",
        "Rice",
        "WTI",
        "Brent",
        "Dubai",
        "BDI",
        "BCI",
        "BPI",
        "BSI",
    ]

    table_rows_html = ""
    for m in target_metrics:
      m_data = all_metrics_data.get(m, {})
      val_2w = [m_data[d] for d in prev_2week_dates if d in m_data]
      avg_2w = sum(val_2w) / len(val_2w) if val_2w else None

      val_1w = [m_data[d] for d in prev_1week_dates if d in m_data]
      avg_1w = sum(val_1w) / len(val_1w) if val_1w else None

      if avg_2w and avg_1w and avg_2w != 0:
        pct_change = ((avg_1w - avg_2w) / avg_2w) * 100
        color = (
            "red" if pct_change > 0 else ("blue" if pct_change < 0 else "black")
        )
        change_str = f"<span style='color:{color}; font-weight:bold;'>{pct_change:+.2f}%</span>"
        avg_2w_str = f"{avg_2w:,.2f}"
        avg_1w_str = f"{avg_1w:,.2f}"
      else:
        change_str = "-"
        avg_2w_str = "-"
        avg_1w_str = "-"

      table_rows_html += (
          f"<tr><td>{m}</td><td>{avg_1w_str}</td><td>{avg_2w_str}</td><td>{change_str}</td></tr>"
      )

    weekly_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Weekly Market Summary ({current_monday})</title>
            <style>
                body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', Arial, sans-serif; padding: 25px; line-height: 1.6; color: #333; }}
                h1 {{ border-bottom: 2px solid #243642; padding-bottom: 10px; color: #243642; }}
                h2 {{ background: #F0F4F8; padding: 10px 14px; border-left: 5px solid #1E3E62; margin-top: 30px; font-size: 19px; }}
                table {{ margin: 15px auto; border-collapse: collapse; width: 95%; text-align: center; }}
                th {{ background-color: #243642; color: #FFFFFF; padding: 8px; font-size: 13px; }}
                td {{ padding: 6px 10px; border: 1px solid #D0D0D0; font-size: 13px; }}
            </style>
        </head>
        <body>
            <h1>📊 주간 시장 종합 요약 (기준일: {current_monday} 월요일)</h1>
            <h2>1. 주요 품목 및 지표 주간 평균 비교</h2>
            <p><b>1주 전 기간:</b> {prev_1week_dates[0]} ~ {prev_1week_dates[-1]} | <b>2주 전 기간:</b> {prev_2week_dates[0]} ~ {prev_2week_dates[-1]}</p>
            
            <table>
                <tr><th>품목 / 지표</th><th>1주 전 평균</th><th>2주 전 평균</th><th>증감률 (%)</th></tr>
                {table_rows_html}
            </table>

            <h2>2. 주간 종합 시황 요약</h2>
            <ul>
                <li><b>곡물 시장:</b> {prev_1week_dates[0]} ~ {prev_1week_dates[-1]} 기간 동안의 주요 곡물 선물 및 FOB 가격은 수확 진척도와 글로벌 수급 이슈에 따라 등락을 보였습니다.</li>
                <li><b>원유 시장:</b> 지정학적 리스크 및 산유국 동향이 반영되며 WTI, 브렌트, 두바이유의 주간 평균 가격이 조정되었습니다.</li>
                <li><b>해상운임 시장:</b> 건화물선 부문의 선종별(BDI, BCI 등) 시황 변동에 연동되어 주간 운임 평균값이 형성되었습니다.</li>
            </ul>
        </body>
        </html>
        """
    with open(weekly_filename, "w", encoding="utf-8") as wf:
      wf.write(weekly_html)


# 주간 요약 자동 생성 실행
generate_weekly_reports(REPORT_DIR)

# 세션 상태 초기화
if "nav_mode" not in st.session_state:
  st.session_state.nav_mode = "Daily"
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None
if "selected_weekly" not in st.session_state:
  st.session_state.selected_weekly = None

# [KMI 스타일 단순화] 사이드바 상단에 Daily / Weekly 전환 버튼 배치
st.sidebar.title("📅 리포트 아카이브")
col1, col2 = st.sidebar.columns(2)

with col1:
  if st.button("Daily", use_container_width=True):
    st.session_state.nav_mode = "Daily"
    st.rerun()
with col2:
  if st.button("Weekly", use_container_width=True):
    st.session_state.nav_mode = "Weekly"
    st.rerun()

st.sidebar.markdown("---")

# 모드별 리포트 딕셔너리 로드
if st.session_state.nav_mode == "Daily":
  reports_dict = get_available_reports(REPORT_DIR, prefix="Daily_Report")
  current_selected_key = "selected_date"
else:
  reports_dict = get_available_reports(REPORT_DIR, prefix="Weekly_Report")
  current_selected_key = "selected_weekly"

if not reports_dict:
  st.sidebar.warning("등록된 리포트가 없습니다.")
  st.title("📈 시장 브리핑 아카이브")
  st.info(
      "해당하는 리포트 파일이 없거나, 주간 요약 생성을 위한 2주치(10영업일 이상)"
      " 일일 리포트가 부족합니다."
  )
else:
  date_list = list(reports_dict.keys())

  if st.session_state[current_selected_key] not in reports_dict:
    st.session_state[current_selected_key] = date_list[0]

  current_key = st.session_state[current_selected_key]

  # 소제목과 높이 정렬을 위한 미세 여백
  st.sidebar.markdown(
      "<div style='margin-top: 10px;'></div>", unsafe_allow_html=True
  )

  # 날짜 버튼 목록 출력
  for date_str in date_list:
    is_selected = date_str == current_key
    btn_type = "primary" if is_selected else "secondary"

    if st.sidebar.button(
        f"📌  {date_str}",
        key=f"btn_{st.session_state.nav_mode}_{date_str}",
        type=btn_type,
        use_container_width=True,
    ):
      st.session_state[current_selected_key] = date_str
      st.rerun()

  # 메인 화면 영역 (선택된 HTML 본문 렌더링)
  file_path = reports_dict[current_key]

  try:
    with open(file_path, "r", encoding="utf-8") as f:
      html_content = f.read()

    # HTML 내부 여백 제거 및 위치 정렬 스타일 주입
    custom_style = (
        "<style>\n body { padding: 0px !important; margin: 0px !important;"
        " background-color: transparent !important; }\n h1 { margin-top: 0px"
        " !important; padding-top: 0px !important; }\n</style>"
    )
    if "<head>" in html_content:
      html_content = html_content.replace("<head>", f"<head>\n{custom_style}")
    else:
      html_content = custom_style + html_content

    # 화면에 리포트 렌더링
    components.html(html_content, height=1350, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 발생했습니다: {e}")
