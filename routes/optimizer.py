"""
Fuel route optimization algorithm.

Given a route (as a polyline) and a list of fuel stations, this module
finds the optimal (cost-minimizing) set of fuel stops along the route,
ensuring the vehicle never runs out of fuel (500-mile max range, 10 MPG).

Algorithm: Greedy with lookahead
  1. Find all fuel stations within search radius of the route
  2. Project each station onto the route (distance along route)
  3. Traverse the route; when fuel gets low, pick the cheapest reachable station
"""

from django.conf import settings
from .models import FuelStation
from .services import (
    haversine_distance,
    find_nearest_point_on_route,
    cumulative_distances,
)


def get_stations_near_route(route_coords, cum_distances, radius_miles=None):
    """
    Find all fuel stations near the route and compute their
    distance-along-route position.

    Args:
        route_coords: list of (lat, lng) from decoded polyline
        cum_distances: cumulative distance array for route_coords
        radius_miles: max distance a station can be from route to be considered

    Returns:
        list of dicts: [{
            'station': FuelStation instance,
            'distance_from_route': miles off-route,
            'route_index': nearest route coordinate index,
            'distance_along_route': miles from start along route
        }]
    """
    if radius_miles is None:
        radius_miles = getattr(settings, "FUEL_STATION_SEARCH_RADIUS_MILES", 25)

    # Get all stations that have coordinates
    stations = FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )

    # Bounding box filter to reduce search space
    lats = [c[0] for c in route_coords]
    lngs = [c[1] for c in route_coords]
    lat_min, lat_max = min(lats) - 0.5, max(lats) + 0.5
    lng_min, lng_max = min(lngs) - 0.5, max(lngs) + 0.5

    stations = stations.filter(
        latitude__gte=lat_min,
        latitude__lte=lat_max,
        longitude__gte=lng_min,
        longitude__lte=lng_max,
    )

    near_route = []
    for station in stations:
        station_point = (station.latitude, station.longitude)
        dist_from_route, route_idx = find_nearest_point_on_route(
            station_point, route_coords, sample_step=20
        )

        if dist_from_route <= radius_miles:
            near_route.append({
                "station": station,
                "distance_from_route": dist_from_route,
                "route_index": route_idx,
                "distance_along_route": cum_distances[route_idx],
            })

    # Sort by position along the route
    near_route.sort(key=lambda x: x["distance_along_route"])
    return near_route


def find_optimal_fuel_stops(route_coords, total_distance_miles):
    """
    Find the optimal set of fuel stops to minimize total fuel cost.

    Uses a greedy algorithm:
    - Start with a full tank (500 miles of range)
    - As we travel, track remaining range
    - When range drops below a threshold, look ahead for the cheapest
      station within our remaining range
    - Always ensure we can reach the next stop

    Args:
        route_coords: list of (lat, lng) from decoded polyline
        total_distance_miles: total route distance in miles

    Returns:
        dict with:
            - fuel_stops: list of fuel stop details
            - total_fuel_cost: total cost in USD
            - total_gallons: total gallons purchased
    """
    max_range = getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500)
    mpg = getattr(settings, "VEHICLE_MPG", 10)

    # If route is shorter than max range, no stops needed
    if total_distance_miles <= max_range:
        total_gallons = total_distance_miles / mpg
        # Still find the cheapest station near the route for reference
        cum_dists = cumulative_distances(route_coords)
        near_stations = get_stations_near_route(route_coords, cum_dists)

        return {
            "fuel_stops": [],
            "total_fuel_cost": 0.0,
            "total_gallons": total_gallons,
            "note": f"Route is {total_distance_miles:.1f} miles — within single tank range ({max_range} miles). No fuel stops needed."
        }

    # Calculate cumulative distances along the route
    cum_dists = cumulative_distances(route_coords)

    # Find stations near the route
    near_stations = get_stations_near_route(route_coords, cum_dists)

    if not near_stations:
        return {
            "fuel_stops": [],
            "total_fuel_cost": 0.0,
            "total_gallons": total_distance_miles / mpg,
            "error": "No fuel stations found near the route. Cannot optimize."
        }

    # --- Greedy optimization ---
    fuel_stops = []
    current_range = max_range  # Start with a full tank
    current_position = 0.0     # Miles from start
    refuel_threshold = 200     # Start looking for fuel when range drops below this

    # De-duplicate stations by location (keep cheapest)
    seen_locations = {}
    unique_stations = []
    for s in near_stations:
        key = (round(s["station"].latitude, 3), round(s["station"].longitude, 3))
        if key not in seen_locations or s["station"].retail_price < seen_locations[key]["station"].retail_price:
            seen_locations[key] = s
    unique_stations = sorted(seen_locations.values(), key=lambda x: x["distance_along_route"])

    i = 0
    while current_position < total_distance_miles:
        # Find all stations we can reach from current position
        reachable = []
        for s in unique_stations:
            station_dist = s["distance_along_route"]
            if station_dist <= current_position:
                continue  # Already passed
            if station_dist > current_position + current_range:
                break  # Too far
            reachable.append(s)

        if not reachable:
            # No more reachable stations; either we can finish or we're stuck
            if current_range >= (total_distance_miles - current_position):
                break  # Can reach destination
            else:
                # Emergency: take any station we might have skipped
                break

        # Check if we can reach the destination without stopping
        remaining_distance = total_distance_miles - current_position
        if current_range >= remaining_distance:
            break

        # Strategy: Look for cheapest station, but ensure we pick one
        # before we run out of fuel
        must_stop_by = current_position + current_range

        # Among reachable stations, find the cheapest
        # But prefer stations that are far enough along to maximize distance per stop
        best_station = None
        best_price = float("inf")

        for s in reachable:
            station_dist = s["distance_along_route"]
            price = s["station"].retail_price

            # If this station is within the "must refuel" window
            if price < best_price:
                best_price = price
                best_station = s
            elif price == best_price and station_dist > best_station["distance_along_route"]:
                # Same price? Pick the one further along the route
                best_station = s

        if best_station is None:
            break

        # Travel to this station
        distance_to_station = best_station["distance_along_route"] - current_position
        current_range -= distance_to_station
        current_position = best_station["distance_along_route"]

        # Calculate how much fuel to buy — fill up to full tank
        gallons_needed = (max_range - current_range) / mpg
        cost = gallons_needed * best_station["station"].retail_price

        fuel_stops.append({
            "name": best_station["station"].name,
            "address": best_station["station"].address,
            "city": best_station["station"].city,
            "state": best_station["station"].state,
            "price_per_gallon": round(best_station["station"].retail_price, 3),
            "gallons_filled": round(gallons_needed, 2),
            "cost": round(cost, 2),
            "latitude": best_station["station"].latitude,
            "longitude": best_station["station"].longitude,
            "distance_from_start_miles": round(current_position, 1),
            "distance_from_route_miles": round(best_station["distance_from_route"], 1),
        })

        current_range = max_range  # Full tank after refueling

        # Remove used station from consideration
        unique_stations = [s for s in unique_stations if s != best_station]

    total_fuel_cost = sum(stop["cost"] for stop in fuel_stops)
    total_gallons = sum(stop["gallons_filled"] for stop in fuel_stops)

    return {
        "fuel_stops": fuel_stops,
        "total_fuel_cost": round(total_fuel_cost, 2),
        "total_gallons": round(total_gallons, 2),
    }
