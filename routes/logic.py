import requests
import polyline
import json
from decimal import Decimal
from functools import lru_cache
from geopy.distance import geodesic
from .models import FuelStation

class RouteOptimizer:
    def __init__(self, range_miles=500, mpg=10):
        self.range_miles = float(range_miles)
        self.mpg = float(mpg)

    @lru_cache(maxsize=128)
    def get_route_data(self, start_lat, start_lng, finish_lat, finish_lng):
        """
        Fetches route from OSRM with LRU caching to minimize API hits.
        """
        url = f"https://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{finish_lng},{finish_lat}"
        response = requests.get(url, params={"overview": "full", "geometries": "polyline"})
        response.raise_for_status()
        data = response.json()
        
        if data['code'] != 'Ok':
            raise Exception("Routing API failed to find a path")
            
        route = data['routes'][0]
        return {
            'polyline': route['geometry'],
            'distance_miles': float(route['distance'] * 0.000621371),
            'coords': polyline.decode(route['geometry'])
        }

    def find_stops(self, route_coords, total_dist):
        """
        Greedy Lookahead Strategy.
        Filters stations within a 10-mile corridor of the route.
        """
        if total_dist <= self.range_miles:
            return [], 0.0

        # Pre-calculate distances for route points
        points_with_dist = []
        acc_dist = 0.0
        prev_coord = route_coords[0]
        for coord in route_coords:
            acc_dist += geodesic(prev_coord, coord).miles
            points_with_dist.append({'coord': coord, 'dist': acc_dist})
            prev_coord = coord

        # Optimization: Bounding box filtering
        lats = [c[0] for c in route_coords]
        lngs = [c[1] for c in route_coords]
        
        candidates = FuelStation.objects.filter(
            latitude__range=(min(lats)-0.2, max(lats)+0.2),
            longitude__range=(min(lngs)-0.2, max(lngs)+0.2)
        )

        stops = []
        current_dist = 0.0
        
        while current_dist < total_dist - 50:
            if total_dist - current_dist <= self.range_miles:
                break
            
            must_stop_by = current_dist + self.range_miles
            
            best_station = None
            min_price = Decimal('inf')
            
            # Sample points in the next window
            target_points = [p for p in points_with_dist if current_dist < p['dist'] <= must_stop_by]
            if not target_points: break

            # Efficient lookup for stations near the segment
            for station in candidates:
                s_coord = (station.latitude, station.longitude)
                # Check distance against sampled points (every 10th for speed)
                for p in target_points[::10]:
                    if geodesic(s_coord, p['coord']).miles < 10:
                        if station.retail_price < min_price:
                            min_price = station.retail_price
                            best_station = station
                        break

            if not best_station: break
                
            stops.append(best_station)
            s_coord = (best_station.latitude, best_station.longitude)
            closest_p = min(target_points, key=lambda p: geodesic(s_coord, p['coord']).miles)
            current_dist = closest_p['dist']

        if not stops: return [], 0.0
            
        avg_price = float(sum(s.retail_price for s in stops) / len(stops))
        total_cost = (total_dist / 10.0) * avg_price
        
        return stops, total_cost
