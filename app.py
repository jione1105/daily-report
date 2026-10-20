import os
import re
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정 (와이드 레이아웃)
st.set_page_config(
    page_title="일일 곡물 및 원자재 시장 브리핑 아카이브",
    page_icon="📈",
    layout="wide",
)

# [CSS 스타일] 사이드바 타이틀, 실선 위치 정렬 및 선택된 날짜 버튼 음영(파란/하늘색 계열) 커스텀
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
        
        /* 현재 선택된 날짜 버튼을 채도 낮은 부드러운 하늘/파란색 계열로 음영 처리 */
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

# 리포트가 저장되는 폴더 경로
REPORT_DIR = "."
os.makedirs(REPORT_DIR, exist_ok=True)


def get_available_reports(directory):
  """폴더 안의 HTML 리포트 파일명에서 날짜를 추출하여 최신순 정렬"""
  reports = {}
  if not os.path.exists(directory):
    return reports

  for f in os.listdir(directory):
    match = re.search(r"Daily_Report\((\d{4}-\d{2}-\d{2})\)\.html", f)
    if match:
      date_str = match[1]
      reports[date_str] = os.path.join(directory, f)

  return dict(sorted(reports.items(), key=lambda x: x[0], reverse=True))


# 세션 상태 초기화
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None

# 사이드바 타이틀 ('일일 리포트 아카이브')
st.sidebar.title("📅 일일 리포트 아카이브")
st.sidebar.markdown("---")

reports_dict = get_available_reports(REPORT_DIR)

if not reports_dict:
  st.sidebar.warning("등록된 리포트가 없습니다.")
  st.title("📈 일일 곡물 및 원자재 시장 브리핑")
  st.info("reports_storage 폴더에 HTML 리포트 파일들을 넣어주세요.")
else:
  date_list = list(reports_dict.keys())

  if st.session_state.selected_date not in reports_dict:
    st.session_state.selected_date = date_list[0]

  # 사이드바 실선 아래와 첫 번째 날짜 버튼 사이 미세 여백 (우측 소제목과 높이 일치화)
  st.sidebar.markdown(
      "<div style='margin-top: 24px;'></div>", unsafe_allow_html=True
  )

  # 날짜 버튼 목록 배치 (현재 보고 있는 날짜에만 은은한 하늘/파란색 음영 적용)
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

    # HTML 파일 내부의 자체 여백(padding)을 제거하여 좌우 시작점 일치화
    custom_style = (
        "<style>\n body { padding: 0px !important; margin: 0px !important;"
        " background-color: transparent !important; }\n h1 { margin-top: 0px"
        " !important; padding-top: 0px !important; }\n</style>"
    )
    if "<head>" in html_content:
      html_content = html_content.replace("<head>", f"<head>\n{custom_style}")
    else:
      html_content = custom_style + html_content

    # HTML 리포트 본문 출력
    components.html(html_content, height=1350, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 발생했습니다: {e}")
