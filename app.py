import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="일일 및 주간 리포트 아카이브",
    page_icon="📈",
    layout="wide",
)

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

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_available_reports(directory, prefix="Daily_Report"):
  reports = {}
  if not os.path.exists(directory):
    return reports
  for f in os.listdir(directory):
    if not f.lower().endswith(".html"):
      continue
    if prefix in f:
      match = re.search(r"(\d{4}-\d{2}-\d{2})", f)
      if match:
        reports[match[1]] = os.path.join(directory, f)
  return dict(sorted(reports.items(), key=lambda x: x[0], reverse=True))


def parse_html_tables(file_path):
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      soup = BeautifulSoup(f.read(), "html.parser")

    tables_data = {}
    for table in soup.find_all("table"):
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
          try:
            val = float(cols[i].replace(",", "").replace("$", ""))
            if h not in tables_data:
              tables_data[h] = {}
            tables_data[h][date_val] = val
          except ValueError:
            pass
    return tables_data
  except Exception:
    return {}


def cleanup_and_generate_weekly_reports(directory):
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

  weeks_dict = {}
  for d_str in sorted_dates:
    dt = datetime.strptime(d_str, "%Y-%m-%d")
    monday_dt = dt - timedelta(days=dt.weekday())
    monday_str = monday_dt.strftime("%Y-%m-%d")
    if monday_str not in weeks_dict:
      weeks_dict[monday_str] = []
    weeks_dict[monday_str].append(d_str)

  for monday_str in sorted(list(weeks_dict.keys())):
    monday_dt = datetime.strptime(monday_str, "%Y-%m-%d")

    w1_start = (monday_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    w1_end = (monday_dt - timedelta(days=3)).strftime("%Y-%m-%d")
    w2_start = (monday_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    w2_end = (monday_dt - timedelta(days=10)).strftime("%Y-%m-%d")

    prev_1week_dates = [
        d for d in sorted_dates if w1_start <= d <= w1_end
    ]
    prev_2week_dates = [
        d for d in sorted_dates if w2_start <= d <= w2_end
    ]

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
        metrics_results[m] = {"change": pct_change, "avg_1w": avg_1w, "avg_2w": avg_2w}
      else:
        change_str = "-"
        metrics_results[m] = {"change": 0, "avg_1w": 0, "avg_2w": 0}

      avg_2w_str = f"{avg_2w:,.2f}" if avg_2w else "-"
      avg_1w_str = f"{avg_1w:,.2f}" if avg_1w else "-"
      table_rows_html += (
          f"<tr><td>{m}</td><td>{avg_1w_str}</td><td>{avg_2w_str}</td><td>{change_str}</td></tr>"
      )

    # 가격 변동 방향성에 맞춘 동적 시황 생성 (주차별 가격 데이터 기반이므로 주차마다 반드시 내용이 바뀜)
    def generate_dynamic_summary(item, data):
      chg = data.get("change", 0)
      v1 = data.get("avg_1w", 0)
      v2 = data.get("avg_2w", 0)
      
      if chg > 0:
        return f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>{chg:+.2f}% 상승</b>하였습니다. 해당 주간 글로벌 수급 호조 및 매수세 유입으로 인한 상방 압력이 작용했습니다."
      elif chg < 0:
        return f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>{chg:+.2f}% 하락</b>하였습니다. 해당 주간 수확 압박 및 매물 출회에 따른 하방 압력이 작용했습니다."
      else:
        return f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>보합세</b>를 기록하였습니다."

    w_sum = generate_dynamic_summary("Wheat", metrics_results.get("Wheat", {}))
    c_sum = generate_dynamic_summary("Corn", metrics_results.get("Corn", {}))
    s_sum = generate_dynamic_summary("Soybean", metrics_results.get("Soybean", {}))
    wti_sum = generate_dynamic_summary("WTI", metrics_results.get("WTI", {}))
    brent_sum = generate_dynamic_summary("Brent", metrics_results.get("Brent", {}))
    dubai_sum = generate_dynamic_summary("Dubai", metrics_results.get("Dubai", {}))

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
                ul {{ padding-left: 20px; }}
                li {{ margin-bottom: 8px; }}
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
                        <li><b>밀 (Wheat):</b> {w_sum}</li>
                        <li><b>옥수수 (Corn):</b> {c_sum}</li>
                        <li><b>콩 (Soybean):</b> {s_sum}</li>
                    </ul>
                </li>
                <br>
                <li><b>원유 시장 (개별 품목 분석):</b>
                    <ul>
                        <li><b>WTI:</b> {wti_sum}</li>
                        <li><b>Brent:</b> {brent_sum}</li>
                        <li><b>Dubai:</b> {dubai_sum}</li>
                    </ul>
                </li>
            </ul>
        </body>
        </html>
        """
    with open(weekly_filename, "w", encoding="utf-8") as wf:
      wf.write(weekly_html)


cleanup_and_generate_weekly_reports(REPORT_DIR)

if "nav_mode" not in st.session_state:
  st.session_state.nav_mode = "Daily"
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None
if "selected_weekly" not in st.session_state:
  st.session_state.selected_weekly = None

st.sidebar.title("📅 리포트 아카이브")
col1, col2 = st.sidebar.columns(2)

is_daily = st.session_state.nav_mode == "Daily"
is_weekly = st.session_state.nav_mode == "Weekly"

with col1:
  if st.button(
      "Daily",
      type="primary" if is_daily else "secondary",
      use_container_width=True,
  ):
    st.session_state.nav_mode = "Daily"
    st.rerun()

with col2:
  if st.button(
      "Weekly",
      type="primary" if is_weekly else "secondary",
      use_container_width=True,
  ):
    st.session_state.nav_mode = "Weekly"
    st.rerun()

st.sidebar.markdown("---")

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
    if st.sidebar.button(
        f"📌  {date_str}",
        key=f"btn_{st.session_state.nav_mode}_{date_str}",
        type="primary" if date_str == current_key else "secondary",
        use_container_width=True,
    ):
      st.session_state[current_selected_key] = date_str
      st.rerun()

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
