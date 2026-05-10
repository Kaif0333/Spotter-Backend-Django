import requests
import polyline
from decimal import Decimal
from geopy.distance import geodesic
from .models import FuelStation

class RouteOptimizer:
    def __init__(self, range_miles=500, mpg=10):
        self.range_miles = range_miles
        self.mpg = mpg

    def get_route_data(self, start_coords, finish_coords):
        url = f"https://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{finish_coords[1]},{finish_coords[0]}"
        response = requests.get(url, params={"overview": "full", "geometries": "polyline", "steps": "true"})
        response.raise_for_status()
        data = response.json()
        
        if data['code'] != 'Ok':
            raise Exception("Routing API failed")
            
        route = data['routes'][0]
        return {
            'polyline': route['geometry'],
            'distance_miles': route['distance'] * 0.000621371,
            'coords': polyline.decode(route['geometry'])
        }

    def find_stops(self, route_coords, total_dist):
        """
        Calculates optimal fuel stops. 
        We sample the route every few miles and find the cheapest station 
        within a reachable radius when fuel gets low.
        """
        if total_dist <= self.range_miles:
            return [], 0

        # Pre-calculate cumulative distance along the route waypoints
        points_with_dist = []
        acc_dist = 0
        prev_coord = route_coords[0]
        for coord in route_coords:
            acc_dist += geodesic(prev_coord, coord).miles
            points_with_dist.append({'coord': coord, 'dist': acc_dist})
            prev_coord = coord

        # Get stations that have been geocoded
        all_stations = FuelStation.objects.filter(latitude__isnull=False)
        
        stops = []
        last_stop_dist = 0 # Miles from start
        
        while last_stop_dist < total_dist - (self.range_miles * 0.1):
            if total_dist - last_stop_dist <= self.range_miles:
                break # Can reach destination
            
            # The point we MUST fuel by
            must_fuel_by = last_stop_dist + self.range_miles
            
            # Find the best station in the window (last_stop_dist + 100 to must_fuel_by)
            best_station = None
            min_price = Decimal('inf')
            
            # Find all points on route within the next window
            target_points = [p for p in points_with_dist if last_stop_dist < p['dist'] <= must_fuel_by]
            if not target_points:
                break
                
            # For each candidate station, check if it's near any of these points
            # To stay fast, we use a rough bounding box first
            lats = [p['coord'][0] for p in target_points]
            lngs = [p['coord'][1] for p in target_points]
            
            candidates = all_stations.filter(
                latitude__range=(min(lats)-0.1, max(lats)+0.1),
                longitude__range=(min(lngs)-0.1, max(lngs)+0.1)
            )

            for station in candidates:
                s_coord = (station.latitude, station.longitude)
                # Optimization: Find distance to the closest point in our target window
                # If it's < 10 miles from any route point, it's "along the route"
                for p in target_points[::10]: # Sample points for speed
                    if geodesic(s_coord, p['coord']).miles < 10:
                        if station.retail_price < min_price:
                            min_price = station.retail_price
                            best_station = station
                        break

            if not best_station:
                # If no station found, algorithm fails to find a path
                break
                
            stops.append(best_station)
            # Update position: find the distance along the route of the point nearest the station
            # For simplicity, we use the distance of the point we were targeting
            s_coord = (best_station.latitude, best_station.longitude)
            closest_p = min(target_points, key=lambda p: geodesic(s_coord, p['coord']).miles)
            last_stop_dist = closest_p['dist']

        # Cost calculation based on distance and station prices
        if not stops:
            return [], 0
            
        avg_price = sum(s.retail_price for s in stops) / len(stops)
        total_cost = (Decimal(str(total_dist)) / Decimal('10')) * avg_price
        
        return stops, total_cost
