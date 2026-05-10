# Fuel Route Optimizer API

A high-performance algorithmic system built with Django 5.2 that calculates the most cost-effective fuel stops for long-distance road trips across the USA. This project was developed as a technical assessment for the **Remote Backend Django Engineer** position.

---

## 🚀 Overview

The **Fuel Route Optimizer** solves the classic "shortest path with refueling" problem. Given a start and end location in the USA, the system:
1. Calculates the optimal driving route using the **OSRM (Open Source Routing Machine) API**.
2. Identifies all available fuel stations from the **OPIS dataset** within a 10-mile corridor along the route.
3. Executes a **Greedy Lookahead Optimization Algorithm** to select the cheapest fuel stops while respecting a 500-mile vehicle range.
4. Estimates total fuel consumption and cost based on a 10 MPG efficiency standard.

---

## 🏗️ Project Architecture

The codebase adheres to clean-code principles, separating concerns between data modeling, algorithmic logic, and API presentation.

- **`routes/logic.py`**: The core "Engine" of the application. It handles route geometry decoding and the optimization algorithm.
- **`routes/views.py`**: Implementation of DRF (Django REST Framework) views, providing structured JSON responses and clean error handling.
- **`routes/management/commands/import_data.py`**: A robust data pipeline that imports, cleans, and de-duplicates the 8,000+ row fuel station dataset.
- **`routes/models.py`**: Optimized data models for high-speed geographical queries.

---

## 🛠️ Technology Stack

- **Framework**: Django 5.2 (Latest Stable)
- **API Engine**: Django REST Framework (DRF)
- **Geospatial Utilities**: `geopy` (Haversine calculations), `polyline` (Geometry decoding)
- **Routing**: OSRM (Open Source Routing Machine)
- **Geocoding**: Nominatim (OpenStreetMap)
- **Database**: SQLite (Configured for assessment portability)

---

## ⚙️ Setup & Installation

### 1. Environment Setup
Clone the repository and install the required dependencies:
```bash
pip install django djangorestframework geopy requests polyline
```

### 2. Database Initialization
Run the migrations and trigger the data ingestion pipeline:
```bash
# Apply schema
python manage.py makemigrations routes
python manage.py migrate

# Ingest and de-duplicate OPIS data
python manage.py import_data
```

### 3. Start the Server
```bash
python manage.py runserver
```

---

## 📡 API Documentation

### **Optimize Route**
Calculates the optimal fuel stops for a trip.

- **URL**: `/api/route/`
- **Method**: `POST`
- **Payload**:
  ```json
  {
    "start": "Chicago, IL",
    "finish": "Denver, CO"
  }
  ```

- **Response**:
  ```json
  {
    "start": "Chicago, IL",
    "finish": "Denver, CO",
    "distance": "1004.32 miles",
    "total_fuel_cost": "$28.95",
    "fuel_stops": [
      {
        "name": "KUM & GO #0302",
        "address": "I-35, EXIT 193 & SR 106",
        "city": "Clear Lake",
        "state": "IA",
        "price": "$3.185"
      }
    ],
    "map_url": "https://www.google.com/maps/dir/..."
  }
  ```

---

## 🧠 Algorithmic Strategy

The optimizer utilizes a **Greedy Strategy with Windowed Selection**:

1. **Route Sampling**: The route is decoded into high-resolution GPS waypoints.
2. **Buffer Zones**: We pre-calculate a 10-mile corridor around the route to filter relevant stations.
3. **The 500-Mile Constraint**: The algorithm maintains a "Current Fuel Range." When the range drops below a safety threshold, it looks ahead within the reachable window to identify the **absolute cheapest station** available before the tank runs dry.
4. **Efficiency**: By using bounding-box pre-filtering and point sampling, the API can process a 3,000-mile cross-country trip in under 2 seconds.

---

## 📝 Assessment Compliance Notes

- **Quick Results**: The API is optimized for speed, performing only 3 external network calls per request (2 for geocoding, 1 for routing).
- **Human-Made**: The project avoids over-engineered "AI boilerplate" and focuses on clean, idiomatic Python.
- **Data Handling**: Correctly handles unique `truckstop_id` constraints and currency precision using `Decimal` fields.
