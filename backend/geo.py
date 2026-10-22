"""Weather and place names. All free, no keys needed (Open-Meteo, BigDataCloud)."""
import json

import requests

import config

_LOC_FILE = config.DATA_DIR / "location.json"
DEFAULT_PLACE = {"name": "Chennai", "lat": 13.0827, "lon": 80.2707}

WMO = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 81: "rain showers",
    82: "violent rain showers", 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def save_location(name: str, lat: float, lon: float) -> None:
    _LOC_FILE.write_text(json.dumps({"name": name, "lat": lat, "lon": lon}), encoding="utf-8")


def last_location() -> dict:
    try:
        return json.loads(_LOC_FILE.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_PLACE)


def reverse_geocode(lat: float, lon: float) -> str:
    try:
        r = requests.get("https://api.bigdatacloud.net/data/reverse-geocode-client", params={
            "latitude": lat, "longitude": lon, "localityLanguage": "en"}, timeout=6).json()
        parts = [r.get("locality") or r.get("city"), r.get("principalSubdivision")]
        name = ", ".join(p for p in parts if p)
        return name or "Your location"
    except Exception:
        return "Your location"


def geocode(city: str) -> dict | None:
    try:
        r = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1}, timeout=6).json()
        hit = (r.get("results") or [None])[0]
        if not hit:
            return None
        return {"name": hit["name"], "lat": hit["latitude"], "lon": hit["longitude"]}
    except Exception:
        return None


def get_weather(lat: float, lon: float) -> dict:
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
    }, timeout=8)
    r.raise_for_status()
    c = r.json()["current"]
    return {
        "temp_c": round(c["temperature_2m"]),
        "feels_c": round(c["apparent_temperature"]),
        "humidity": c["relative_humidity_2m"],
        "wind_kmh": round(c["wind_speed_10m"]),
        "text": WMO.get(int(c["weather_code"]), "unknown conditions"),
        "is_day": bool(c.get("is_day", 1)),
    }
