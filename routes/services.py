"""
External API services for routing and geocoding.

Uses OSRM (Open Source Routing Machine) for route calculation — free, no API key.
Uses Nominatim (OpenStreetMap) for geocoding city/state to lat/lng.
"""

import math
import requests
import polyline as polyline_codec
from geopy.distance import geodesic


# ---------------------------------------------------------------------------
# OSRM Routing
# ---------------------------------------------------------------------------

OSRM_BASE_URL = "https://router.project-osrm.org"


def get_route(start_coords, end_coords):
    """
    Get a driving route between two coordinate pairs using OSRM.

    Args:
        start_coords: (latitude, longitude) of start
        end_coords: (latitude, longitude) of end

    Returns:
        dict with keys:
            - distance_miles: total route distance
            - duration_seconds: estimated driving time
            - geometry: encoded polyline string
            - waypoints: list of [lng, lat] coordinate pairs decoded from polyline
    """
    # OSRM expects lon,lat order
    start_str = f"{start_coords[1]},{start_coords[0]}"
    end_str = f"{end_coords[1]},{end_coords[0]}"

    url = f"{OSRM_BASE_URL}/route/v1/driving/{start_str};{end_str}"
    params = {
        "overview": "full",          # Full route geometry
        "geometries": "polyline",    # Encoded polyline format
        "steps": "false",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(f"OSRM routing failed: {data.get('message', 'Unknown error')}")

    route = data["routes"][0]
    encoded_polyline = route["geometry"]

    # Decode polyline to list of (lat, lng) tuples
    decoded_coords = polyline_codec.decode(encoded_polyline)

    return {
        "distance_miles": route["distance"] * 0.000621371,  # meters to miles
        "duration_seconds": route["duration"],
        "geometry": encoded_polyline,
        "waypoints": decoded_coords,  # list of (lat, lng) tuples
    }


# ---------------------------------------------------------------------------
# Geocoding via Nominatim
# ---------------------------------------------------------------------------

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode_location(location_string):
    """
    Geocode a location string (e.g. 'New York, NY' or 'Los Angeles, CA')
    to (latitude, longitude) using Nominatim.

    Args:
        location_string: Human-readable location within the USA

    Returns:
        (latitude, longitude) tuple or None if geocoding failed
    """
    params = {
        "q": f"{location_string}, USA",
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
    }
    headers = {
        "User-Agent": "FuelRouteOptimizer/1.0 (fuel-route-assessment)"
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        results = response.json()
        if results:
            return (float(results[0]["lat"]), float(results[0]["lon"]))
    except Exception as e:
        print(f"Geocoding failed for '{location_string}': {e}")

    return None


def geocode_city_state(city, state):
    """
    Geocode a city/state pair to (latitude, longitude).

    Args:
        city: City name
        state: 2-letter US state abbreviation

    Returns:
        (latitude, longitude) tuple or None
    """
    return geocode_location(f"{city.strip()}, {state.strip()}")


# ---------------------------------------------------------------------------
# Geometric / Distance utilities
# ---------------------------------------------------------------------------

def haversine_distance(coord1, coord2):
    """
    Calculate the great-circle distance between two points in miles.

    Args:
        coord1: (lat, lng) tuple
        coord2: (lat, lng) tuple

    Returns:
        Distance in miles
    """
    return geodesic(coord1, coord2).miles


def find_nearest_point_on_route(point, route_coords, sample_step=10):
    """
    Find the nearest point on a route to a given point.
    Samples every `sample_step` points for performance.

    Args:
        point: (lat, lng) tuple
        route_coords: list of (lat, lng) tuples from decoded polyline
        sample_step: check every Nth point for performance

    Returns:
        (min_distance_miles, nearest_route_index)
    """
    min_dist = float("inf")
    nearest_idx = 0

    for i in range(0, len(route_coords), sample_step):
        dist = haversine_distance(point, route_coords[i])
        if dist < min_dist:
            min_dist = dist
            nearest_idx = i

    # Refine search around the best candidate
    start = max(0, nearest_idx - sample_step)
    end = min(len(route_coords), nearest_idx + sample_step)
    for i in range(start, end):
        dist = haversine_distance(point, route_coords[i])
        if dist < min_dist:
            min_dist = dist
            nearest_idx = i

    return min_dist, nearest_idx


def cumulative_distances(route_coords, sample_step=5):
    """
    Calculate cumulative distances along a route in miles.
    Samples every `sample_step` points and interpolates for performance.

    Args:
        route_coords: list of (lat, lng) tuples

    Returns:
        list of cumulative distances (in miles) for each coordinate index
    """
    n = len(route_coords)
    distances = [0.0] * n

    for i in range(1, n):
        if i % sample_step == 0 or i == n - 1:
            dist = haversine_distance(route_coords[i - 1], route_coords[i])
            distances[i] = distances[i - 1] + dist
        else:
            # Rough estimate — will be refined at next sample point
            distances[i] = distances[i - 1]

    # Fix any zero gaps by interpolating
    last_known = 0
    for i in range(1, n):
        if distances[i] > distances[last_known]:
            # Interpolate between last_known and i
            if i - last_known > 1:
                step = (distances[i] - distances[last_known]) / (i - last_known)
                for j in range(last_known + 1, i):
                    distances[j] = distances[last_known] + step * (j - last_known)
            last_known = i

    return distances
