# fire_predictor.py
# : CCTV 위치, 시야각, 픽셀 좌표를 기반으로 기상·지형 데이터를 결합해 산불 확산 방향과 속도를 예측하는

import numpy as np
import joblib
from model_trainer import compute_relative_alignment
from gps_utils import pixel_to_gps
from terrain_reader import get_slope_from_geotiff
from weather_api import get_wind_data

def predict_fire_from_image(
    cctv_lat: float,
    cctv_lon: float,
    azimuth_deg: float,
    fov_deg: float,
    image_width: int,
    pixel_x: int,
    geotiff_path: str,
    weather_api_key: str,
    model_path: str = "fire_model.pkl",
    distance_m: float = 100.0
) -> dict:
    # 1. 위치 추정
    lat, lon = pixel_to_gps(cctv_lat, cctv_lon, azimuth_deg, fov_deg, image_width, pixel_x, dist_m=distance_m)

    # 2. 지형 정보 추출
    slope_deg = get_slope_from_geotiff(geotiff_path, lat, lon)

    # 3. 실시간 기상 정보 획득
    wind_dir, wind_speed = get_wind_data(lat, lon, weather_api_key)

    # 4. 추론
    model = load_model(model_path)
    result = predict_fire_spread(model, wind_dir, wind_speed, slope_deg, azimuth_deg)

    return {
        "gps": (lat, lon),
        "wind_dir": wind_dir,
        "wind_speed": wind_speed,
        "slope_deg": slope_deg,
        "slope_dir": azimuth_deg,
        "spread_dir": result["spread_dir"],
        "spread_speed": result["spread_speed"]
    }

# 학습된 모델 loading
def load_model(model_path: str = "fire_model.pkl"):

    return joblib.load(model_path)

# 입력된 조건에 대해 산불 확산 방향 및 속도를 예측
def predict_fire_spread(model, wind_dir: float, wind_speed: float, slope_deg: float, slope_dir: float) -> dict:

    relative_angle = compute_relative_alignment(wind_dir, slope_dir)
    X = np.array([[wind_dir, wind_speed, slope_deg, slope_dir, relative_angle]])
    pred = model.predict(X)[0]

    return {
        "spread_dir": pred[0],
        "spread_speed": pred[1]
    }

def main():
    # 예시용 설정값
    cctv_lat = 37.4563
    cctv_lon = 126.7052
    azimuth_deg = 135.0
    fov_deg = 90.0
    image_width = 1920
    pixel_x = 800
    geotiff_path = "Slope_All.tif"
    weather_api_key = "iSXe1sI1w2nT2V9Vumutg1he0nmtCd7jKdMMe0egafjbreLf36ABQziAqJ0sUxhLIIF1QcAzkaydtg%2FL6NlcFA%3D%3D"  # 기상청 단기예보 API
    model_path = "fire_model.pkl"

    print("🔥 이미지 기반 산불 예측 테스트 시작 🔥")
    result = predict_fire_from_image(
        cctv_lat=cctv_lat,
        cctv_lon=cctv_lon,
        azimuth_deg=azimuth_deg,
        fov_deg=fov_deg,
        image_width=image_width,
        pixel_x=pixel_x,
        geotiff_path=geotiff_path,
        weather_api_key=weather_api_key,
        model_path=model_path
    )

    print("\n추정 위치 (GPS):", result["gps"])
    print(f"풍향: {result['wind_dir']:.1f}°, 풍속: {result['wind_speed']:.2f} m/s")
    print(f"경사도: {result['slope_deg']:.1f}°, 경사 방향: {result['slope_dir']:.1f}°")
    print(f"\n예상 확산 방향: {result['spread_dir']:.1f}°")
    print(f"예상 확산 속도: {result['spread_speed']:.2f} m/s")

if __name__ == "__main__":
    main()