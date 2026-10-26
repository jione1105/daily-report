import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정 (와이드 레이아웃)
st.set_page_config(
    page_title="일일 및 주간 리포트 아카이브",
    page_icon="📈",
    layout="wide",
)

# [CSS 스타일] 사이드바 정렬 및 탭 디자인 커스텀
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
  """일일 HTML 파일 안의 테이블에서 지표 수치 추출"""
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


def parse_daily_commentaries(file_path):
  """일일 HTML 파일에서 품목별 시황 원문 파싱 (팜유 혼입 방지)"""
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      soup = BeautifulSoup(f.read(), "html.parser")

    commentaries = {}
    for h3 in soup.find_all("h3"):
      title = h3.get_text(strip=True)
      key = None
      if "Wheat" in title:
        key = "Wheat"
      elif "Corn" in title:
        key = "Corn"
      elif "Soybean" in title:
        key = "Soybean"
      elif "Crude Oil" in title:
        key = "CrudeOil"

      if key:
        sentences = []
        curr = h3.find_next_sibling()
        while curr and curr.name not in ["h2", "h3", "h1"]:
          for el in curr.find_all(["p", "li"]):
            txt = el.get_text(strip=True)
            if (
                txt
                and len(txt) > 30
                and "Reporting by" not in txt
                and "Update for market close" not in txt
                and "Updates with closing prices" not in txt
            ):
              clean_txt = re.sub(r"^[A-Z\s,]+ \(Reuters\) - ", "", txt)
              if clean_txt not in sentences:
                sentences.append(clean_txt)
          curr = curr.find_next_sibling()

        if key not in commentaries:
          commentaries[key] = []
        commentaries[key].extend(sentences)
    return commentaries
  except Exception:
    return {}


def translate_text(text):
  """영어 문장을 자연스러운 한국어로 번역"""
  if not text or not text.strip():
    return text
  try:
    translated = GoogleTranslator(source="en", target="ko").translate(text)
    return translated if translated else text
  except Exception:
    return text


def cleanup_and_generate_weekly_reports(directory):
  """월요일 기준 주간 파일 자동 생성"""
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
  daily_comms_map = {}
  for d_str, f_path in daily_reports.items():
    daily_data_map[d_str] = parse_html_tables(f_path)
    daily_comms_map[d_str] = parse_daily_commentaries(f_path)

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

    prev_1week_dates = [d for d in sorted_dates if w1_start <= d <= w1_end]
    prev_2week_dates = [d for d in sorted_dates if w2_start <= d <= w2_end]

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
        metrics_results[m] = {
            "change": pct_change,
            "avg_1w": avg_1w,
            "avg_2w": avg_2w,
        }
      else:
        change_str = "-"
        metrics_results[m] = {"change": 0, "avg_1w": 0, "avg_2w": 0}

      avg_2w_str = f"{avg_2w:,.2f}" if avg_2w else "-"
      avg_1w_str = f"{avg_1w:,.2f}" if avg_1w else "-"
      table_rows_html += f"<tr><td>{m}</td><td>{avg_1w_str}</td><td>{avg_2w_str}</td><td>{change_str}</td></tr>"

    def get_price_driven_market_commentary(item_key, change_val):
      if change_val > 0:
        trend_kws = [
            "rose",
            "gain",
            "higher",
            "increase",
            "up",
            "rally",
            "surge",
            "growth",
            "stoked",
            "highest",
        ]
        dir_text = "상승"
      elif change_val < 0:
        trend_kws = [
            "fall",
            "fell",
            "drop",
            "lower",
            "decline",
            "decrease",
            "down",
            "pressure",
            "slip",
            "eased",
        ]
        dir_text = "하락"
      else:
        trend_kws = []
        dir_text = "보합"

      lookup_key = (
          "CrudeOil" if item_key in ["WTI", "Brent", "Dubai"] else item_key
      )
      matched_sentences = []

      # 1주 전 5일치 일일 리포트 원문을 모두 순회하며 등락 방향성 키워드가 포함된 알맹이 원인 문장 추출
      for d_str in prev_1week_dates:
        comms = daily_comms_map.get(d_str, {}).get(lookup_key, [])
        for s in comms:
          s_lower = s.lower()
          # 유종별 세부 필터링
          if item_key == "WTI" and not (
              "wti" in s_lower or "west texas" in s_lower or "clc1" in s_lower
          ):
            continue
          if item_key == "Brent" and not (
              "brent" in s_lower or "lcoc1" in s_lower
          ):
            continue
          if item_key == "Dubai" and not (
              "dubai" in s_lower
              or "middle east" in s_lower
              or "saudi" in s_lower
          ):
            continue

          if any(kw in s_lower for kw in trend_kws):
            if s not in matched_sentences:
              matched_sentences.append(s)

      # 매칭된 문장이 없다면 일반 시황 문장 중 첫 번째 것을 활용
      if not matched_sentences:
        for d_str in prev_1week_dates:
          comms = daily_comms_map.get(d_str, {}).get(lookup_key, [])
          if comms and comms[0] not in matched_sentences:
            matched_sentences.append(comms[0])

      # 추출된 핵심 원인 문장들을 한국어로 번역하여 최대 2개(약 2줄 분량)로 구성
      translated_lines = []
      for eng_s in matched_sentences[:2]:
        ko_s = translate_text(eng_s)
        if ko_s:
          translated_lines.append(ko_s)

      if not translated_lines:
        summary_text = (
            f"해당 주간 {item_key} 시장은 수급 및 대외 요인에 따라 변동성을"
            " 나타냈습니다."
        )
      else:
        summary_text = " ".join(translated_lines)

      v1 = metrics_results.get(item_key, {}).get("avg_1w", 0)
      v2 = metrics_results.get(item_key, {}).get("avg_2w", 0)

      summary_html = f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>{change_val:+.2f}% {dir_text}</b>하였습니다.<br><span style='color: #444; font-size: 13px; display: block; margin-top: 4px;'><b>[변동 원인 요약]</b> {summary_text}</span>"
      return summary_html

    w_sum = get_price_driven_market_commentary("Wheat", metrics_results.get("Wheat", {}).get("change", 0))
    c_sum = get_price_driven_market_commentary("Corn", metrics_results.get("Corn", {}).get("change", 0))
    s_sum = get_price_driven_market_commentary("Soybean", metrics_results.get("Soybean", {}).get("change", 0))
    wti_sum = get_price_driven_market_commentary("WTI", metrics_results.get("WTI", {}).get("change", 0))
    brent_sum = get_price_driven_market_commentary("Brent", metrics_results.get("Brent", {}).get("change", 0))
    dubai_sum = get_price_driven_market_commentary("Dubai", metrics_results.get("Dubai", {}).get("change", 0))

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
                li {{ margin-bottom: 12px; }}
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
