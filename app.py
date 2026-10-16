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
    # Daily_Report(YYYY-MM-DD).html 패턴 매칭
    match = re.search(r"Daily_Report\((\d{4}-\d{2}-\d{2})\)\.html", f)
    if match:
      date_str = match[1]
      reports[date_str] = os.path.join(directory, f)

  return dict(sorted(reports.items(), key=lambda x: x[0], reverse=True))


# 세션 상태에 선택된 날짜 초기화
if "selected_date" not in st.session_state:
  st.session_state.selected_date = None

# 사이드바 구성 (KMI 브리핑 스타일 목록형)
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

  # 초기 선택값 설정 (가장 최신 날짜)
  if st.session_state.selected_date not in reports_dict:
    st.session_state.selected_date = date_list[0]

  # 드롭다운이 아닌 버튼(목록) 형태로 모든 날짜 표시
  st.sidebar.markdown("### 🗓️ 리포트 일자 목록")
  for date_str in date_list:
    # 현재 선택된 날짜인지 확인하여 버튼 스타일 다르게 표시 (선택 강조)
    is_selected = date_str == st.session_state.selected_date
    button_type = "primary" if is_selected else "secondary"

    if st.sidebar.button(
        f"📌  {date_str}", key=f"btn_{date_str}", use_container_width=True
    ):
      st.session_state.selected_date = date_str
      st.rerun()

  st.sidebar.markdown("---")
  st.sidebar.info(
      "💡 좌측 목록에서 날짜를 클릭하면 해당 일자의 리포트가 우측에 표시됩니다."
  )

  # 메인 화면 영역 (중복 제목 제거 및 본문 즉시 출력)
  selected_date = st.session_state.selected_date
  file_path = reports_dict[selected_date]

  try:
    with open(file_path, "r", encoding="utf-8") as f:
      html_content = f.read()

    # 상단 헤더 대신 선택된 날짜 정보만 깔끔하게 상단에 바 형태로 표시하고 바로 본문 렌더링
    st.markdown(
        f"### 📋 Daily Grain & Macro Market Report : **{selected_date}**"
    )
    st.markdown("---")

    # 기존 HTML 리포트 본문 출력 (내부 제목과 중복되지 않도록 컴포넌트 렌더링)
    components.html(html_content, height=1300, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 발생했습니다: {e}")
