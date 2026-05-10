from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from geopy.geocoders import Nominatim
from .logic import RouteOptimizer

class FuelRouteView(APIView):
    """
    Endpoint: POST /api/route/
    Payload: { "start": "...", "finish": "..." }
    """
    
    def post(self, request):
        start_loc = request.data.get('start')
        finish_loc = request.data.get('finish')
        
        if not start_loc or not finish_loc:
            return Response({"error": "Start and finish are required"}, status=400)

        geocoder = Nominatim(user_agent="fuel_optimizer_app")
        
        try:
            # Geocode locations
            start = geocoder.geocode(start_loc)
            finish = geocoder.geocode(finish_loc)
            
            if not start or not finish:
                return Response({"error": "Location not found"}, status=400)
                
            optimizer = RouteOptimizer()
            
            # 1. Get Route
            route = optimizer.get_route_data((start.latitude, start.longitude), (finish.latitude, finish.longitude))
            
            # 2. Find Stops
            stops, total_cost = optimizer.find_stops(route['coords'], route['distance_miles'])
            
            return Response({
                "start": start_loc,
                "finish": finish_loc,
                "distance": f"{route['distance_miles']:.2f} miles",
                "total_fuel_cost": f"${total_cost:.2f}",
                "fuel_stops": [
                    {
                        "name": s.name,
                        "address": s.address,
                        "city": s.city,
                        "state": s.state,
                        "price": f"${s.retail_price}"
                    } for s in stops
                ],
                "map_url": f"https://www.google.com/maps/dir/{start.latitude},{start.longitude}/{finish.latitude},{finish.longitude}"
                # Polyline also provided for frontend maps
                #"polyline": route['polyline']
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class HomeView(APIView):
    """
    Simple landing page for the root URL.
    """
    def get(self, request):
        return Response({
            "message": "Welcome to the Fuel Route Optimizer API",
            "endpoints": {
                "route_optimization": "/api/route/ (POST)"
            },
            "status": "operational"
        })
