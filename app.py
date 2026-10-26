import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai
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

# Google Gemini API 클라이언트 초기화
google_api_key = st.secrets.get(
    "GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY", "")
)
if google_api_key:
  genai.configure(api_key=google_api_key)


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
  """일일 HTML 파일에서 품목별 시황 원문 파싱"""
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
                and len(txt) > 25
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


def generate_ai_market_summary(item_key, change_val, v1, v2, raw_texts):
  """Google Gemini API를 활용하여 시황 원문 분석 및 한국어 요약 생성"""
  dir_text = "상승" if change_val > 0 else ("하락" if change_val < 0 else "보합")

  if not google_api_key:
    return f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>{change_val:+.2f}% {dir_text}</b>하였습니다.<br><span style='color:red;'>[알림] GOOGLE_API_KEY가 설정되지 않았습니다.</span>"

  filtered_texts = []
  for t in raw_texts:
    t_lower = t.lower()
    if item_key in ["WTI", "Brent", "Dubai"]:
      if (
          item_key.lower() in t_lower
          or "crude" in t_lower
          or "oil" in t_lower
          or "saudi" in t_lower
      ):
        filtered_texts.append(t)
    else:
      filtered_texts.append(t)

  target_corpus = (
      "\n".join(filtered_texts[:15]) if filtered_texts else "관련 주요 뉴스 원문 없음"
  )

  prompt = f"""
  당신은 글로벌 원자재 및 에너지 시장 전문 수석 애널리스트입니다.
  다음은 최근 1주일간 수집된 '{item_key}' 품목의 일일 시장 뉴스 원문들입니다:
  
  ---
  {target_corpus}
  ---
  
  이 품목의 주간 평균 가격은 2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})으로 {change_val:+.2f}% 변화하여 '{dir_text}' 세를 보였습니다.
  위 뉴스 원문과 가격 변동률을 바탕으로, 이 품목의 주간 가격 변동 핵심 원인과 시장 동향을 전문적인 비즈니스 한국어 톤으로 2~3문장 이내로 명확하게 요약해 주세요. 다른 서두 없이 요약 본문만 작성해 주세요.
  """

  try:
    # Gemini 모델 호출 (gemini-1.5-flash 사용)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    ai_summary = response.text.strip()
  except Exception as e:
    ai_summary = f"AI 요약 생성 중 오류가 발생했습니다: {e}"

  summary_html = f"2주 전 평균({v2:,.2f}) 대비 1주 전 평균({v1:,.2f})이 <b>{change_val:+.2f}% {dir_text}</b>하였습니다.<br><span style='color: #444; font-size: 13px; display: block; margin-top: 5px;'><b>[AI 애널리스트 시황 요약]</b> {ai_summary}</span>"
  return summary_html


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

    def build_summary_for_item(item_key):
      res = metrics_results.get(item_key, {"change": 0, "avg_1w": 0, "avg_2w": 0})
      chg = res["change"]
      v1 = res["avg_1w"]
      v2 = res["avg_2w"]

      lookup_key = (
          "CrudeOil" if item_key in ["WTI", "Brent", "Dubai"] else item_key
      )
      raw_pool = []
      for d_str in prev_1week_dates:
        comms = daily_comms_map.get(d_str, {}).get(lookup_key, [])
        raw_pool.extend(comms)

      return generate_ai_market_summary(item_key, chg, v1, v2, raw_pool)

    w_sum = build_summary_for_item("Wheat")
    c_sum = build_summary_for_item("Corn")
    s_sum = build_summary_for_item("Soybean")
    wti_sum = build_summary_for_item("WTI")
    brent_sum = build_summary_for_item("Brent")
    dubai_sum = build_summary_for_item("Dubai")

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
                li {{ margin-bottom: 10px; }}
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
