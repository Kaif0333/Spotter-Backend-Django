"""
DRF serializers for route optimization API.
"""

from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Validates incoming route optimization requests."""

    start = serializers.CharField(
        max_length=500,
        help_text="Start location (e.g., 'New York, NY')"
    )
    finish = serializers.CharField(
        max_length=500,
        help_text="Finish location (e.g., 'Los Angeles, CA')"
    )


class FuelStopSerializer(serializers.Serializer):
    """Serializes a single fuel stop along the route."""

    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price_per_gallon = serializers.FloatField()
    gallons_filled = serializers.FloatField()
    cost = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_from_start_miles = serializers.FloatField()
    distance_from_route_miles = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    """Serializes the full route optimization response."""

    start = serializers.CharField()
    finish = serializers.CharField()
    total_distance_miles = serializers.FloatField()
    total_duration_hours = serializers.FloatField()
    total_fuel_cost_usd = serializers.FloatField()
    total_gallons_used = serializers.FloatField()
    fuel_stops = FuelStopSerializer(many=True)
    route_polyline = serializers.CharField(
        help_text="Encoded polyline for rendering on a map"
    )
