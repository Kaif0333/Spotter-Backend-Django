"""
Management command to load fuel station data from CSV and geocode stations.

Usage:
    python manage.py load_fuel_data                      # Load CSV only
    python manage.py load_fuel_data --geocode             # Load + geocode all
    python manage.py load_fuel_data --geocode --limit 50  # Load + geocode first 50
"""

import csv
import time
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from routes.models import FuelStation
from routes.services import geocode_city_state


# US state abbreviations for validation
US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC',
}


class Command(BaseCommand):
    help = "Load fuel station data from CSV file and optionally geocode stations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=os.path.join(settings.BASE_DIR, "fuel-prices-for-be-assessment.csv"),
            help="Path to the CSV file (default: project root)",
        )
        parser.add_argument(
            "--geocode",
            action="store_true",
            help="Geocode stations after loading (uses Nominatim — rate-limited)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit geocoding to N unique city/state pairs (0 = all)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing fuel station data before loading",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]
        do_geocode = options["geocode"]
        limit = options["limit"]
        clear = options["clear"]

        if clear:
            count = FuelStation.objects.count()
            FuelStation.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing stations"))

        # --- Step 1: Load CSV ---
        self.stdout.write(f"Loading fuel data from: {csv_path}")
        self._load_csv(csv_path)

        # --- Step 2: Geocode (optional) ---
        if do_geocode:
            self._geocode_stations(limit)

        # Summary
        total = FuelStation.objects.count()
        geocoded = FuelStation.objects.filter(latitude__isnull=False).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nDone! {total} stations loaded, {geocoded} geocoded."
        ))

    def _load_csv(self, csv_path):
        """Load fuel stations from CSV, de-duplicating by cheapest price per location."""
        created = 0
        skipped = 0

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f"  Found {len(rows)} rows in CSV")

        # Group by (OPIS ID, City, State) and keep cheapest price
        station_map = {}
        for row in rows:
            try:
                opis_id = int(row["OPIS Truckstop ID"])
                name = row["Truckstop Name"].strip()
                address = row["Address"].strip()
                city = row["City"].strip()
                state = row["State"].strip().upper()
                rack_id = int(row["Rack ID"])
                price = float(row["Retail Price"])

                # Filter: only US states
                if state not in US_STATES:
                    skipped += 1
                    continue

                key = (opis_id, city, state)
                if key not in station_map or price < station_map[key]["retail_price"]:
                    station_map[key] = {
                        "opis_id": opis_id,
                        "name": name,
                        "address": address,
                        "city": city,
                        "state": state,
                        "rack_id": rack_id,
                        "retail_price": price,
                    }
            except (ValueError, KeyError) as e:
                skipped += 1
                continue

        # Bulk create
        stations_to_create = []
        for data in station_map.values():
            stations_to_create.append(FuelStation(**data))

        FuelStation.objects.bulk_create(stations_to_create, ignore_conflicts=True)
        created = len(stations_to_create)

        self.stdout.write(f"  Created {created} unique stations (skipped {skipped} non-US/duplicate rows)")

    def _geocode_stations(self, limit):
        """Geocode stations by unique city/state pairs."""
        # Get unique city/state pairs that need geocoding
        stations_to_geocode = FuelStation.objects.filter(
            latitude__isnull=True
        ).values_list("city", "state").distinct()

        unique_pairs = list(set(stations_to_geocode))
        if limit > 0:
            unique_pairs = unique_pairs[:limit]

        total = len(unique_pairs)
        self.stdout.write(f"\n  Geocoding {total} unique city/state pairs...")

        geocoded = 0
        failed = 0

        for i, (city, state) in enumerate(unique_pairs):
            coords = geocode_city_state(city, state)

            if coords:
                # Update all stations with this city/state
                FuelStation.objects.filter(
                    city=city, state=state, latitude__isnull=True
                ).update(latitude=coords[0], longitude=coords[1])
                geocoded += 1
            else:
                failed += 1

            # Progress update every 50
            if (i + 1) % 50 == 0:
                self.stdout.write(f"    Progress: {i+1}/{total} ({geocoded} ok, {failed} failed)")

            # Rate limit: Nominatim requires max 1 req/sec
            time.sleep(1.1)

        self.stdout.write(f"  Geocoded {geocoded} pairs, {failed} failed")
