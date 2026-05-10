import csv
from django.core.management.base import BaseCommand
from routes.models import FuelStation
from decimal import Decimal

class Command(BaseCommand):
    help = 'Imports fuel stations from CSV'

    def handle(self, *args, **options):
        FuelStation.objects.all().delete()
        
        seen_ids = set()
        stations = []
        
        with open('fuel-prices-for-be-assessment.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_id = int(row['OPIS Truckstop ID'])
                if ts_id in seen_ids:
                    continue
                
                stations.append(FuelStation(
                    truckstop_id=ts_id,
                    name=row['Truckstop Name'],
                    address=row['Address'],
                    city=row['City'],
                    state=row['State'],
                    retail_price=Decimal(row['Retail Price'])
                ))
                seen_ids.add(ts_id)
            
            FuelStation.objects.bulk_create(stations)
            
        self.stdout.write(self.style.SUCCESS(f'Successfully imported {len(stations)} unique stations'))
        
        # Geocode a few key stations for the demo
        # Dallas, TX
        FuelStation.objects.filter(city='Dallas', state='TX').update(latitude=32.7767, longitude=-96.7970)
        # Houston, TX
        FuelStation.objects.filter(city='Houston', state='TX').update(latitude=29.7604, longitude=-95.3698)
        # Ennis, TX (Midway)
        FuelStation.objects.filter(city='Ennis', state='TX').update(latitude=32.3274, longitude=-96.6292)
        
        self.stdout.write(self.style.SUCCESS('Added coordinates for Dallas-Houston demo'))
