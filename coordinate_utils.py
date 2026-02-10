"""
Coordinate Utilities - VN-2000 to WGS84 Conversion
Chuyển đổi tọa độ VN-2000 (EPSG:3405) sang WGS84 cho actual map
"""

import numpy as np
from typing import Tuple, Union

# Try pyproj for accurate conversion
try:
    from pyproj import Transformer
    _HAS_PYPROJ = True
except ImportError:
    _HAS_PYPROJ = False

# VN-2000 UTM zone 48N (EPSG:3405) - covers Mekong Delta
# WGS84 (EPSG:4326)
SOURCE_CRS = "EPSG:3405"  # VN-2000 / UTM zone 48N
TARGET_CRS = "EPSG:4326"  # WGS84

# Approximate bounds for Mekong Delta in VN-2000 (meters)
# Easting: 416k-730k, Northing: 1.03M-1.22M
VN2000_Mekong_BOUNDS = {
    'x_min': 416000, 'x_max': 732000,
    'y_min': 1033000, 'y_max': 1222000
}

# WGS84 bounds for Mekong Delta
WGS84_MEKONG_BOUNDS = {
    'lat_min': 9.35, 'lat_max': 11.04,
    'lon_min': 104.24, 'lon_max': 107.11
}


def _is_vn2000_coords(x: float, y: float) -> bool:
    """Check if coordinates are in VN-2000 range (meters)."""
    return (
        VN2000_Mekong_BOUNDS['x_min'] <= x <= VN2000_Mekong_BOUNDS['x_max'] and
        VN2000_Mekong_BOUNDS['y_min'] <= y <= VN2000_Mekong_BOUNDS['y_max']
    )


def _is_wgs84_coords(lat: float, lon: float) -> bool:
    """Check if coordinates are in WGS84 range (degrees)."""
    return (
        WGS84_MEKONG_BOUNDS['lat_min'] <= lat <= WGS84_MEKONG_BOUNDS['lat_max'] and
        WGS84_MEKONG_BOUNDS['lon_min'] <= lon <= WGS84_MEKONG_BOUNDS['lon_max']
    )


def convert_vn2000_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """
    Chuyển đổi tọa độ VN-2000 UTM zone 48N (mét) sang WGS84 (độ).
    
    Args:
        x: Easting (mét) - VN-2000
        y: Northing (mét) - VN-2000
        
    Returns:
        (lat, lon) tuple in WGS84 degrees
    """
    if _HAS_PYPROJ:
        try:
            transformer = Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)
            lon, lat = transformer.transform(float(x), float(y))
            return (float(lat), float(lon))
        except Exception:
            pass
    
    # Fallback: approximate affine transformation for Mekong Delta
    # VN-2000 UTM 48N bounds: Easting 416k-732k -> lon 104.24-107.11
    #                        Northing 1.03M-1.22M -> lat 9.35-11.04
    x = float(x)
    y = float(y)
    lon = 104.24 + (x - 416000) * (107.11 - 104.24) / (732000 - 416000)
    lat = 9.35 + (y - 1033000) * (11.04 - 9.35) / (1222000 - 1033000)
    return (lat, lon)


def convert_coords_to_wgs84(
    x_or_lon: Union[float, np.ndarray],
    y_or_lat: Union[float, np.ndarray],
    source: str = 'auto'
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Chuyển đổi tọa độ sang WGS84. Tự động phát hiện định dạng nguồn.
    
    Args:
        x_or_lon: Easting (VN-2000) hoặc longitude (WGS84)
        y_or_lat: Northing (VN-2000) hoặc latitude (WGS84)
        source: 'VN2000', 'WGS84', hoặc 'auto' (tự phát hiện)
        
    Returns:
        (lat, lon) trong WGS84
    """
    x = np.asarray(x_or_lon, dtype=float)
    y = np.asarray(y_or_lat, dtype=float)
    
    if source == 'auto':
        # Sample first value for detection
        x0, y0 = float(x.flat[0]) if x.size > 0 else 0, float(y.flat[0]) if y.size > 0 else 0
        if _is_vn2000_coords(x0, y0):
            source = 'VN2000'
        elif _is_wgs84_coords(y0, x0):  # WGS84: (lat, lon) or (lon, lat)
            # Nếu lat lon swapped: x có thể là lat (9-11), y là lon (104-107)
            if 9 <= x0 <= 12 and 100 <= y0 <= 110:
                return (x, y)  # Already (lat, lon)

    if source == 'WGS84':
        return (y, x) if x.size == 1 else (y, x)
    
    if source == 'VN2000' or _is_vn2000_coords(float(x.flat[0]), float(y.flat[0])):
        if x.size == 1:
            return convert_vn2000_to_wgs84(float(x), float(y))
        lats, lons = [], []
        for xi, yi in zip(x.flat, y.flat):
            lat, lon = convert_vn2000_to_wgs84(float(xi), float(yi))
            lats.append(lat)
            lons.append(lon)
        return (np.array(lats).reshape(x.shape), np.array(lons).reshape(y.shape))
    
    return (y, x)  # Assume already WGS84
