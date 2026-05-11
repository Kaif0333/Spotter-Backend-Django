from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from geopy.geocoders import Nominatim
from functools import lru_cache
from .logic import RouteOptimizer

# Professional Geocoder with Caching
@lru_cache(maxsize=128)
def get_coordinates(location_str):
    geocoder = Nominatim(user_agent="fuel_optimizer_v1", timeout=10)
    return geocoder.geocode(location_str)

class FuelRouteView(APIView):
    def post(self, request):
        start_loc = request.data.get('start')
        finish_loc = request.data.get('finish')
        
        if not start_loc or not finish_loc:
            return Response({"error": "Start and finish are required"}, status=400)

        try:
            start = get_coordinates(start_loc)
            finish = get_coordinates(finish_loc)
            
            if not start or not finish:
                return Response({"error": "One or both locations could not be resolved."}, status=400)
                
            optimizer = RouteOptimizer()
            
            # Use cached routing
            route = optimizer.get_route_data(start.latitude, start.longitude, finish.latitude, finish.longitude)
            
            # Find stops
            stops, total_cost = optimizer.find_stops(route['coords'], route['distance_miles'])
            
            return Response({
                "start": start_loc,
                "finish": finish_loc,
                "distance_miles": round(route['distance_miles'], 2),
                "total_fuel_cost_usd": round(total_cost, 2),
                "fuel_stops_count": len(stops),
                "fuel_stops": [
                    {
                        "name": s.name,
                        "address": s.address,
                        "city": s.city,
                        "state": s.state,
                        "price_per_gallon": float(s.retail_price)
                    } for s in stops
                ],
                "map_url": f"https://www.google.com/maps/dir/{start.latitude},{start.longitude}/{finish.latitude},{finish.longitude}"
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class HomeView(APIView):
    def get(self, request):
        return Response({
            "project": "Fuel Route Optimizer API",
            "version": "1.0.0",
            "documentation": "/api/route/ (POST)",
            "status": "online"
        })
