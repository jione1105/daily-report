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

# 리포트가 저장되는 폴더 경로
REPORT_DIR = "reports_storage"
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


# 세션 상태에 선택된 날짜 초기화
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None

# 사이드바 구성 (목록형 날짜 선택)
st.sidebar.title("📅 일일 브리핑 아카이브")
st.sidebar.markdown("조회할 날짜를 선택해주세요.")
st.sidebar.markdown("---")

reports_dict = get_available_reports(REPORT_DIR)

if not reports_dict:
  st.sidebar.warning("등록된 리포트가 없습니다.")
  st.title("📈 일일 곡물 및 원자재 시장 브리핑")
  st.info("현재 아카이브된 리포트가 없습니다.")
else:
  date_list = list(reports_dict.keys())

  if st.session_state.selected_date not in reports_dict:
    st.session_state.selected_date = date_list[0]

  st.sidebar.markdown("### 🗓️ 리포트 일자 목록")
  for date_str in date_list:
    is_selected = date_str == st.session_state.selected_date

    if st.sidebar.button(
        f"📌  {date_str}", key=f"btn_{date_str}", use_container_width=True
    ):
      st.session_state.selected_date = date_str
      st.rerun()

  st.sidebar.markdown("---")

  # 메인 화면 영역 (스트림릿 자체 타이틀을 없애고 HTML 리포트 본문만 출력)
  selected_date = st.session_state.selected_date
  file_path = reports_dict[selected_date]

  try:
    with open(file_path, "r", encoding="utf-8") as f:
      html_content = f.read()

    # HTML 본문만 컴포넌트로 렌더링 (중복 제목 원천 차단)
    components.html(html_content, height=1350, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 화면에 표시되는 도중 오류가 발생했습니다: {e}")
