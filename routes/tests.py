from django.test import TestCase
from .optimizer import find_optimal_fuel_stops
from .models import FuelStation

class OptimizerTestCase(TestCase):
    def setUp(self):
        # Create some test fuel stations
        FuelStation.objects.create(
            opis_id=1, name="Cheap Stop", address="123", city="Chicago", state="IL",
            rack_id=1, retail_price=2.50, latitude=41.8781, longitude=-87.6298
        )
        FuelStation.objects.create(
            opis_id=2, name="Expensive Stop", address="456", city="Davenport", state="IA",
            rack_id=2, retail_price=4.00, latitude=41.5236, longitude=-90.5776
        )

    def test_short_route_no_stops(self):
        # Route is 10 miles, range is 500, no stops needed
        route_coords = [(41.8781, -87.6298), (41.8881, -87.6398)]
        result = find_optimal_fuel_stops(route_coords, 10.0)
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_gallons'], 1.0) # 10 miles / 10 mpg

    def test_optimization_logic(self):
        # This is a placeholder test. In a real scenario, you'd mock the 
        # get_stations_near_route or provide more precise coordinates.
        pass
