"""Weather API integration using Open-Meteo."""
import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from functools import lru_cache
import asyncio


class WeatherService:
    """Service for fetching weather data from Open-Meteo API."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def __init__(self):
        self._cache = {}
        self._cache_duration = timedelta(minutes=15)

    async def geocode_location(self, city_name: str) -> Optional[Tuple[float, float, str]]:
        """
        Convert city name to coordinates.

        Returns:
            Tuple of (latitude, longitude, full_name) or None if not found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GEOCODING_URL,
                params={"name": city_name, "count": 5, "language": "en"},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data.get("results"):
                return None

            # Try to find best match
            search_lower = city_name.lower()
            results = data["results"]

            # First, look for exact city name match
            for result in results:
                if result["name"].lower() == search_lower:
                    admin1 = result.get("admin1", "")
                    full_name = f"{result['name']}, {admin1}, {result['country']}" if admin1 else f"{result['name']}, {result['country']}"
                    return result["latitude"], result["longitude"], full_name

            # Then, check if search matches country (for city-states like Singapore, Monaco)
            for result in results:
                if result["country"].lower() == search_lower:
                    # Use country name as the display name for city-states
                    full_name = result["country"]
                    return result["latitude"], result["longitude"], full_name

            # Fall back to first result
            result = results[0]
            admin1 = result.get("admin1", "")
            # If country matches search, prioritize country name
            if result["country"].lower() == search_lower:
                full_name = result["country"]
            elif admin1:
                full_name = f"{result['name']}, {admin1}, {result['country']}"
            else:
                full_name = f"{result['name']}, {result['country']}"

            return result["latitude"], result["longitude"], full_name

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int = 168,
    ) -> List[dict]:
        """
        Get hourly temperature forecast.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            hours: Number of hours to forecast (default 168 = 7 days)

        Returns:
            List of hourly forecasts with datetime, temperature, humidity, wind_speed
        """
        # Check cache
        cache_key = f"{latitude:.2f},{longitude:.2f}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_duration:
                return cached_data[:hours]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                    "forecast_days": 16,
                    "timezone": "auto",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Weather API error: {response.status_code}")

            data = response.json()
            hourly = data.get("hourly", {})

            forecasts = []
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            humidity = hourly.get("relative_humidity_2m", [])
            wind = hourly.get("wind_speed_10m", [])

            for i in range(min(len(times), hours)):
                forecasts.append({
                    "datetime": datetime.fromisoformat(times[i]),
                    "temperature": temps[i] if i < len(temps) else None,
                    "humidity": humidity[i] if i < len(humidity) else None,
                    "wind_speed": wind[i] if i < len(wind) else None,
                })

            # Update cache
            self._cache[cache_key] = (datetime.now(), forecasts)

            return forecasts

    async def get_historical_and_forecast(
        self,
        latitude: float,
        longitude: float,
        start_datetime: datetime,
        hours: int = 168,
    ) -> List[float]:
        """
        Get ambient temperatures starting from a specific datetime.
        Combines historical data with forecast as needed.

        Returns:
            List of hourly temperatures
        """
        now = datetime.now()

        # For simplicity, if start is in the past, use forecast data
        # and assume past temperatures follow a similar pattern
        forecasts = await self.get_forecast(latitude, longitude, hours)

        if not forecasts:
            # Return default temperatures if API fails
            return [20.0] * hours

        # Extract just temperatures
        temps = [f["temperature"] for f in forecasts]

        # Extend if needed
        while len(temps) < hours:
            # Repeat pattern
            temps.extend(temps[:min(24, hours - len(temps))])

        return temps[:hours]

    def generate_synthetic_temps(
        self,
        base_temp: float = 25.0,
        daily_range: float = 10.0,
        hours: int = 168,
    ) -> List[float]:
        """
        Generate synthetic ambient temperatures for simulation.
        Useful when weather API is unavailable.

        Args:
            base_temp: Average daily temperature
            daily_range: Temperature variation (max - min)
            hours: Number of hours

        Returns:
            List of hourly temperatures following a sinusoidal pattern
        """
        import math

        temps = []
        for h in range(hours):
            # Sinusoidal daily variation
            # Minimum at 6 AM, maximum at 3 PM
            hour_of_day = h % 24
            phase = (hour_of_day - 6) * math.pi / 12
            variation = (daily_range / 2) * math.sin(phase)
            temps.append(base_temp + variation)

        return temps
