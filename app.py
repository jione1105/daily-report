import os
import re
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정 (와이드 레이아웃)
st.set_page_config(
    page_title="일일 리포트 아카이브",
    page_icon="📈",
    layout="wide",
)

# [CSS 스타일] 사이드바와 메인 영역 정렬 및 버튼 음영 커스텀
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2.0rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 2.0rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        section[data-testid="stSidebar"] hr {
            margin-left: 0rem !important;
            margin-right: 0rem !important;
        }
        
        /* 현재 선택된 날짜 버튼 음영 (부드러운 하늘/파란색 계열) */
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

# app.py와 HTML 파일들이 함께 있는 현재 폴더(".")를 기준으로 설정
REPORT_DIR = "."


def get_available_reports(directory):
  """폴더 안의 모든 HTML 파일에서 날짜(YYYY-MM-DD)를 유연하게 추출"""
  reports = {}
  if not os.path.exists(directory):
    return reports

  for f in os.listdir(directory):
    if not f.endswith(".html"):
      continue

    # 파일명에서 YYYY-MM-DD 패턴을 유연하게 탐색 (예: Daily_Report(2026-10-16).html 또는 2026-10-16.html 등)
    match = re.search(r"(\d{4}-\d{2}-\d{2})", f)
    if match:
      date_str = match[1]
      reports[date_str] = os.path.join(directory, f)

  # 최신순 정렬
  return dict(sorted(reports.items(), key=lambda x: x[0], reverse=True))


# 세션 상태 초기화
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None

# 사이드바 타이틀
st.sidebar.title("📅 일일 리포트 아카이브")
st.sidebar.markdown("---")

reports_dict = get_available_reports(REPORT_DIR)

if not reports_dict:
  st.sidebar.warning("등록된 리포트가 없습니다.")
  st.title("📈 일일 곡물 및 원자재 시장 브리핑")
  st.info(
      "⚠️ 현재 폴더에 날짜 형식(YYYY-MM-DD)이 포함된 HTML 파일이 없습니다."
      " 파일명을 확인해주세요."
  )
else:
  date_list = list(reports_dict.keys())

  if st.session_state.selected_date not in reports_dict:
    st.session_state.selected_date = date_list[0]

  # 소제목과 높이를 맞추기 위한 미세 여백
  st.sidebar.markdown(
      "<div style='margin-top: 24px;'></div>", unsafe_allow_html=True
  )

  # 날짜 버튼 목록 출력
  for date_str in date_list:
    is_selected = date_str == st.session_state.selected_date
    btn_type = "primary" if is_selected else "secondary"

    if st.sidebar.button(
        f"📌  {date_str}", key=f"btn_{date_str}", type=btn_type, use_container_width=True
    ):
      st.session_state.selected_date = date_str
      st.rerun()

  # 메인 화면 영역 (HTML 본문 렌더링)
  selected_date = st.session_state.selected_date
  file_path = reports_dict[selected_date]

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
