"""
weather_service.py — Enrichissement météo (Open-Meteo, sans clé API).

But : AFFINER les recommandations d'irrigation. Si de la pluie est prévue dans
les prochains jours, inutile (voire contre-productif) d'arroser → on reporte ou
réduit la dose. C'est une enrichissement OPTIONNEL : en cas d'absence de réseau,
le service renvoie {"available": false} et le cœur agronomique (100 % local)
continue de fonctionner normalement.

Open-Meteo est gratuit, sans clé, et autorise un usage non commercial.
Localisation par défaut : plaine du Saïss (Maroc), surchargeable par .env
(WEATHER_LAT / WEATHER_LON).
"""

from __future__ import annotations

import os

import httpx

# Localisation par défaut (plaine du Saïss, Maroc) — surchargeable via .env.
DEFAULT_LAT = float(os.getenv("WEATHER_LAT", "33.9"))
DEFAULT_LON = float(os.getenv("WEATHER_LON", "-5.55"))
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT", "8"))

# Seuils d'ajustement de l'irrigation selon la pluie cumulée à 3 jours (mm).
_RAIN_SKIP_MM = 10.0     # ≥ 10 mm → irrigation reportée
_RAIN_REDUCE_MM = 4.0    # 4–10 mm → dose réduite de moitié


def _irrigation_from_rain(rain_3d_mm: float) -> dict:
    """Traduit la pluie prévue en consigne d'irrigation (facteur + message)."""
    if rain_3d_mm >= _RAIN_SKIP_MM:
        return {"factor": 0.0, "defer": True,
                "message": f"{rain_3d_mm:.0f} mm de pluie prévus sous 3 j — irrigation reportée."}
    if rain_3d_mm >= _RAIN_REDUCE_MM:
        return {"factor": 0.5, "defer": False,
                "message": f"{rain_3d_mm:.0f} mm de pluie prévus — dose d'irrigation réduite de moitié."}
    return {"factor": 1.0, "defer": False,
            "message": "Pas de pluie significative prévue — irrigation selon le besoin du sol."}


async def get_forecast(lat: float | None = None, lon: float | None = None) -> dict:
    """
    Renvoie un bulletin 3 jours + une consigne d'irrigation dérivée.
    Forme : {available, lat, lon, days:[...], rain_3d_mm, tmax, tmin, irrigation:{...}}
    Ne lève jamais : en cas d'erreur réseau, renvoie {"available": false}.
    """
    lat = DEFAULT_LAT if lat is None else lat
    lon = DEFAULT_LON if lon is None else lon
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "forecast_days": 3, "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT) as client:
            r = await client.get(OPEN_METEO_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return {"available": False}

    daily = data.get("daily", {})
    rain = daily.get("precipitation_sum") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    times = daily.get("time") or []
    rain_3d = round(sum(v for v in rain if isinstance(v, (int, float))), 1)
    days = [
        {"date": times[i] if i < len(times) else None,
         "rain_mm": rain[i] if i < len(rain) else None,
         "tmax": tmax[i] if i < len(tmax) else None,
         "tmin": tmin[i] if i < len(tmin) else None}
        for i in range(min(3, len(times)))
    ]
    return {
        "available": True,
        "lat": lat, "lon": lon,
        "days": days,
        "rain_3d_mm": rain_3d,
        "tmax": tmax[0] if tmax else None,
        "tmin": tmin[0] if tmin else None,
        "irrigation": _irrigation_from_rain(rain_3d),
    }
