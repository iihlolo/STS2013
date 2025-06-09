# gps_utils.py
# : CCTV 카메라 정보와 영상 내 픽셀 좌표를 바탕으로 해당 픽셀의 GPS 좌표 추정

from geopy.distance import geodesic

def pixel_to_gps(
    cctv_lat: float,
    cctv_lon: float,
    azimuth_deg: float,
    fov_deg: float,
    image_width: int,
    pixel_x: int,
    dist_m: float = 100 # 기본 예상 거리 = 100(m)
    ) -> tuple[float, float]:

    relative_pos = (pixel_x - image_width / 2) / (image_width / 2)

    offset_angle = (fov_deg / 2) * relative_pos

    total_bearing = (azimuth_deg + offset_angle) % 360

    spot = geodesic(meters=dist_m).destination((cctv_lat, cctv_lon), total_bearing)

    return spot.latitude, spot.longitude