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

# [CSS 스타일] 사이드바 정렬, 버튼 및 활성 탭 파란색 음영 강조 커스텀
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
  """일일 HTML 파일 안의 모든 테이블에서 날짜별 지표 수치를 정밀하게 추출"""
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      soup = BeautifulSoup(f.read(), "html.parser")

    tables_data = {}
    tables = soup.find_all("table")
    for table in tables:
      rows = table.find_all("tr")
      if len(rows) < 2:
        continue

      headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
      if not headers or "Date" not in headers:
        continue

      date_idx = headers.index("Date")

      for row in rows[1:]:
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cols) <= date_idx:
          continue

        date_val = cols[date_idx]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
          continue

        for i, h in enumerate(headers):
          if i == date_idx or i >= len(cols):
            continue
          raw_val = cols[i].replace(",", "").replace("$", "")
          try:
            val = float(raw_val)
            if h not in tables_data:
              tables_data[h] = {}
            tables_data[h][date_val] = val
          except ValueError:
            pass
    return tables_data
  except Exception:
    return {}


def cleanup_and_generate_weekly_reports(directory):
  """월요일 기준으로 각 주차별 1주 전, 2주 전 데이터를 정확히 매칭하여 주간 리포트 생성"""
  # 잘못 생성된 10월 20일 등 불필요한 주간 파일 정리
  wrong_weekly = os.path.join(directory, "Weekly_Report(2026-10-20).html")
  if os.path.exists(wrong_weekly):
    try:
      os.remove(wrong_weekly)
    except Exception:
      pass

  daily_reports = get_available_reports(directory, prefix="Daily_Report")
  if len(daily_reports) < 5:
    return

  daily_data_map = {}
  for d_str, f_path in daily_reports.items():
    daily_data_map[d_str] = parse_html_tables(f_path)

  sorted_dates = sorted(list(daily_reports.keys()))

  # 월요일 기준으로 주 단위 그룹화
  weeks_dict = {}
  for d_str in sorted_dates:
    dt = datetime.strptime(d_str, "%Y-%m-%d")
    monday_dt = dt - timedelta(days=dt.weekday())
    monday_str = monday_dt.strftime("%Y-%m-%d")
    if monday_str not in weeks_dict:
      weeks_dict[monday_str] = []
    weeks_dict[monday_str].append(d_str)

  sorted_mondays = sorted(list(weeks_dict.keys()))

  for monday_str in sorted_mondays:
    monday_dt = datetime.strptime(monday_str, "%Y-%m-%d")

    # [핵심 수정] 캘린더 기반으로 1주 전(월~금), 2주 전(월~금) 날짜 범위 동적 계산
    w1_start = monday_dt - timedelta(days=7)
    w1_end = monday_dt - timedelta(days=3)
    w1_start_str = w1_start.strftime("%Y-%m-%d")
    w1_end_str = w1_end.strftime("%Y-%m-%d")

    w2_start = monday_dt - timedelta(days=14)
    w2_end = monday_dt - timedelta(days=10)
    w2_start_str = w2_start.strftime("%Y-%m-%d")
    w2_end_str = w2_end.strftime("%Y-%m-%d")

    prev_1week_dates = [
        d for d in sorted_dates if w1_start_str <= d <= w1_end_str
    ]
    prev_2week_dates = [
        d for d in sorted_dates if w2_start_str <= d <= w2_end_str
    ]

    # 데이터가 충분치 않으면 해당 주간 파일 생성 건너뜀
    if not prev_1week_dates or not prev_2week_dates:
      continue

    weekly_filename = os.path.join(directory, f"Weekly_Report({monday_str}).html")

    all_metrics_data = {}
    for d_str in prev_2week_dates + prev_1week_dates:
      t_data = daily_data_map.get(d_str, {})
      for metric, d_map in t_data.items():
        if metric not in all_metrics_data:
          all_metrics_data[metric] = {}
        for d, v in d_map.items():
          all_metrics_data[metric][d] = v

    target_metrics = ["Wheat", "Corn", "Soybean", "WTI", "Brent", "Dubai"]

    metrics_results = {}
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
        metrics_results[m] = {"change": pct_change, "avg_1w": avg_1w}
      else:
        change_str = "-"
        avg_2w_str = "-"
        avg_1w_str = "-"
        metrics_results[m] = {"change": 0, "avg_1w": 0}

      table_rows_html += (
          f"<tr><td>{m}</td><td>{avg_1w_str}</td><td>{avg_2w_str}</td><td>{change_str}</td></tr>"
      )

    def get_dir_text(val):
      return "상승" if val > 0 else ("하락" if val < 0 else "보합")

    wheat_dir = get_dir_text(metrics_results.get("Wheat", {}).get("change", 0))
    corn_dir = get_dir_text(metrics_results.get("Corn", {}).get("change", 0))
    soy_dir = get_dir_text(metrics_results.get("Soybean", {}).get("change", 0))

    wti_dir = get_dir_text(metrics_results.get("WTI", {}).get("change", 0))
    brent_dir = get_dir_text(metrics_results.get("Brent", {}).get("change", 0))
    dubai_dir = get_dir_text(metrics_results.get("Dubai", {}).get("change", 0))

    weekly_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Weekly Market Summary ({monday_str})</title>
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
            <h1>📊 주간 시장 종합 요약 (기준일: {monday_str} 월요일)</h1>
            
            <h2>1. 주요 품목별 가격 변동</h2>
            <p><b>1주 전 기간:</b> {prev_1week_dates[0]} ~ {prev_1week_dates[-1]} | <b>2주 전 기간:</b> {prev_2week_dates[0]} ~ {prev_2week_dates[-1]}</p>
            <table>
                <tr><th>품목 / 지표</th><th>1주 전 평균</th><th>2주 전 평균</th><th>증감률 (%)</th></tr>
                {table_rows_html}
            </table>

            <h2>2. 주간 시황 요약</h2>
            <ul>
                <li><b>곡물 시장 (개별 품목 분석):</b>
                    <ul>
                        <li><b>밀 (Wheat):</b> 2주 전 대비 1주 전 평균 가격이 <b>{wheat_dir}</b>하였습니다. (미국 겨울밀 파종 진행 상황 및 흑해 지역 수출 동향이 반영됨)</li>
                        <li><b>옥수수 (Corn):</b> 2주 전 대비 1주 전 평균 가격이 <b>{corn_dir}</b>하였습니다. (미국 중서부 건조 날씨에 따른 수확 가속화 및 수출 수요 변화가 작용함)</li>
                        <li><b>콩 (Soybean):</b> 2주 전 대비 1주 전 평균 가격이 <b>{soy_dir}</b>하였습니다. (신곡 수확 압박 및 주요국(중국) 수입 수요 증감에 따라 변동성이 나타남)</li>
                    </ul>
                </li>
                <br>
                <li><b>원유 시장 (개별 품목 분석):</b>
                    <ul>
                        <li><b>WTI:</b> 2주 전 대비 1주 전 평균 가격이 <b>{wti_dir}</b>하였습니다. (미국 원유 선물 만기 앞둔 수급 및 재고 이슈가 연동됨)</li>
                        <li><b>Brent:</b> 2주 전 대비 1주 전 평균 가격이 <b>{brent_dir}</b>하였습니다. (글로벌 해상 수송 및 지정학적 공급 차질 우려가 반영됨)</li>
                        <li><b>Dubai:</b> 2주 전 대비 1주 전 평균 가격이 <b>{dubai_dir}</b>하였습니다. (아시아 현물 시장의 수급 및 산유국 공식판매가격(OSP) 추이가 작용함)</li>
                    </ul>
                </li>
            </ul>
        </body>
        </html>
        """
    with open(weekly_filename, "w", encoding="utf-8") as wf:
      wf.write(weekly_html)


# 주간 파일 생성 실행
cleanup_and_generate_weekly_reports(REPORT_DIR)

# 세션 상태 초기화
if "nav_mode" not in st.session_state:
  st.session_state.nav_mode = "Daily"
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None
if "selected_weekly" not in st.session_state:
  st.session_state.selected_weekly = None

# [KMI 스타일] 사이드바 상단에 Daily / Weekly 전환 버튼 배치 (현재 활성 탭에 파란색 음영 강조)
st.sidebar.title("📅 리포트 아카이브")
col1, col2 = st.sidebar.columns(2)

is_daily = st.session_state.nav_mode == "Daily"
is_weekly = st.session_state.nav_mode == "Weekly"

with col1:
  btn_type_d = "primary" if is_daily else "secondary"
  if st.button("Daily", type=btn_type_d, use_container_width=True):
    st.session_state.nav_mode = "Daily"
    st.rerun()

with col2:
  btn_type_w = "primary" if is_weekly else "secondary"
  if st.button("Weekly", type=btn_type_w, use_container_width=True):
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
      "해당하는 리포트 파일이 없거나, 주간 요약 생성을 위한 일일 리포트가"
      " 부족합니다."
  )
else:
  date_list = list(reports_dict.keys())

  if st.session_state[current_selected_key] not in reports_dict:
    st.session_state[current_selected_key] = date_list[0]

  current_key = st.session_state[current_selected_key]

  st.sidebar.markdown(
      "<div style='margin-top: 10px;'></div>", unsafe_allow_html=True
  )

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

    custom_style = (
        "<style>\n body { padding: 0px !important; margin: 0px !important;"
        " background-color: transparent !important; }\n h1 { margin-top: 0px"
        " !important; padding-top: 0px !important; }\n</style>"
    )
    if "<head>" in html_content:
      html_content = html_content.replace("<head>", f"<head>\n{custom_style}")
    else:
      html_content = custom_style + html_content

    components.html(html_content, height=1350, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 발생했습니다: {e}")
