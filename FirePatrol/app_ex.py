import streamlit as st
from fire_predictor import predict_fire_from_image
from terrain_reader import get_slope_from_geotiff
from weather_api import get_wind_data
from gps_utils import pixel_to_gps
import os

MODEL_PATH = "fire_model.h5"
SLOPE_TIF_PATH = "Slope_All.tif
WEATHER_API_KEY = os.getenv("KMA_API_KEY")  # 환경변수에서 기상청 API 키 읽기

st.set_page_config(page_title="산불 확산 예측 대시보드", layout="centered")
st.title("🔥 산불 확산 예측 대시보드")

# 입력 섹션
st.markdown("### 🔧 입력값 설정")
cctv_lat = st.number_input("CCTV 위도", value=37.1234, format="%f")
cctv_lon = st.number_input("CCTV 경도", value=128.1234, format="%f")
azimuth = st.slider("CCTV 설치 방향 (°)", min_value=0, max_value=360, value=90)
fov = st.slider("카메라 화각 (°)", min_value=30, max_value=120, value=90)
image_width = st.number_input("이미지 가로 폭 (px)", min_value=100, max_value=1920, value=1280)
pixel_x = st.slider("확산 추정 대상 픽셀 X좌표", min_value=0, max_value=image_width, value=image_width // 2)
distance = st.slider("추정 거리 (m)", min_value=50, max_value=1000, value=100)

if st.button("🌲 산불 확산 예측 실행"):
    try:
        # 1. 픽셀 → GPS
        lat, lon = pixel_to_gps(cctv_lat, cctv_lon, azimuth, fov, image_width, pixel_x, distance)

        # 2. 경사도 추출
        slope_deg = get_slope_from_geotiff(SLOPE_TIF_PATH, lat, lon)
        slope_dir = azimuth  # 일반적으로 경사 방향은 카메라 방향과 유사하다고 가정

        # 3. 기상청 API로 풍향/풍속 획득
        wind_dir, wind_speed = get_wind_data(lat, lon, WEATHER_API_KEY)

        # 4. 모델 예측 실행
        result = predict_fire_from_image(MODEL_PATH, wind_dir, wind_speed, slope_deg, slope_dir)

        # 5. 결과 출력
        st.success("✅ 예측 성공!")
        st.markdown("### 📈 예측 결과")
        st.write(f"**산불 확산 방향:** {result['spread_dir']:.1f}°")
        st.write(f"**산불 확산 속도:** {result['spread_speed']:.2f} m/s")

    except Exception as e:
        st.error(f"❌ 예측 실패: {str(e)}")
