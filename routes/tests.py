from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import FuelStation
from decimal import Decimal

class FuelRouteTests(APITestCase):
    def setUp(self):
        """Pre-populate a few stations for integration testing."""
        FuelStation.objects.create(
            truckstop_id=9999,
            name="Test Station Dallas",
            address="123 Main St",
            city="Dallas",
            state="TX",
            retail_price=Decimal("3.15"),
            latitude=32.7767,
            longitude=-96.7970
        )
        FuelStation.objects.create(
            truckstop_id=9998,
            name="Test Station Houston",
            address="456 South St",
            city="Houston",
            state="TX",
            retail_price=Decimal("2.95"),
            latitude=29.7604,
            longitude=-95.3698
        )

    def test_home_endpoint(self):
        """Test the landing page returns 200."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("project", response.data)

    def test_route_optimization_api(self):
        """
        Test a real route calculation. 
        Note: This will perform actual external API calls to OSRM/Nominatim.
        """
        url = reverse('fuel-route')
        data = {
            "start": "Dallas, TX",
            "finish": "Houston, TX"
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("distance_miles", response.data)
        self.assertIn("total_fuel_cost_usd", response.data)
        self.assertIn("fuel_stops", response.data)

    def test_invalid_request(self):
        """Test error handling for missing parameters."""
        url = reverse('fuel-route')
        data = {"start": "Dallas, TX"} # Missing finish
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
