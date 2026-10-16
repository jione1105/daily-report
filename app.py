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

# 팀원에게 받은 HTML 리포트들을 모아둘 폴더 설정
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


# 사이드바 구성
st.sidebar.title("📅 일일 브리핑 아카이브")
st.sidebar.markdown(
    "팀원에게 받은 HTML 리포트를 업로드하고 일자별로 조회하세요."
)
st.sidebar.markdown("---")

# 파일 업로더 기능 (팀원에게 받은 HTML 파일을 마우스로 드래그해서 업로드)
uploaded_files = st.sidebar.file_uploader(
    "HTML 리포트 업로드",
    type=["html"],
    accept_multiple_files=True,
    help="팀원에게 받은 Daily_Report(YYYY-MM-DD).html 파일들을 올려주세요.",
)

# 업로드된 파일이 있다면 reports_storage 폴더에 자동으로 저장
if uploaded_files:
  for uploaded_file in uploaded_files:
    file_path = os.path.join(REPORT_DIR, uploaded_file.name)
    if not os.path.exists(file_path):
      with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
  st.sidebar.success("✅ 파일 업로드 완료!")

st.sidebar.markdown("---")

# 저장된 리포트 목록 불러오기
reports_dict = get_available_reports(REPORT_DIR)

if not reports_dict:
  st.sidebar.warning("업로드된 리포트가 없습니다.")
  st.title("📈 일일 곡물 및 원자재 시장 브리핑")
  st.info(
      "👈 좌측 사이드바의 **'HTML 리포트 업로드'** 영역에 팀원에게 받은"
      " 리포트 파일들을 드래그해서 넣어주세요."
  )
else:
  date_list = list(reports_dict.keys())

  # 날짜 선택 셀렉트박스 (KMI 브리핑 형태)
  selected_date = st.sidebar.selectbox(
      "조회 일자 선택", date_list, index=0
  )

  # 선택된 날짜의 HTML 내용 렌더링
  file_path = reports_dict[selected_date]
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      html_content = f.read()

    # 메인 화면 제목
    st.markdown(
        f"### 📋 Daily Grain & Macro Market Report : **{selected_date}**"
    )
    st.markdown("---")

    # 기존 HTML 리포트 화면을 웹 상에 그대로 완벽하게 렌더링
    components.html(html_content, height=1300, scrolling=True)

  except Exception as e:
    st.error(f"리포트를 불러오는 중 오류가 발생했습니다: {e}")