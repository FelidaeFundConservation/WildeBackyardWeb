"""Utility functions for geocoding and reverse geocoding."""
import logging

import requests

logger = logging.getLogger(__name__)


def reverse_geocode_with_nominatim(latitude, longitude):
    """
    Reverse geocode coordinates using Nominatim API.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        dict with locality, state, country, and zip_code, or None if failed
    """
    api_url = "https://nominatim.openstreetmap.org/reverse"
    
    # Per Nominatim usage policy, we must include a User-Agent
    headers = {
        "User-Agent": "WildeBackyard/1.0 (wildlife conservation platform)"
    }

    params = {
        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "addressdetails": 1,
        "zoom": 14,  # Town/city level detail, appropriate for wildlife sightings
    }

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            
            # Extract address components
            address = data.get("address", {})
            
            # Build location data from Nominatim response
            return {
                "locality": (
                    address.get("city") or 
                    address.get("town") or 
                    address.get("village") or 
                    address.get("hamlet") or
                    address.get("suburb") or
                    None
                ),
                "state": (
                    address.get("state") or 
                    address.get("province") or
                    None
                ),
                "country": address.get("country"),
                "zip_code": address.get("postcode"),
            }
        else:
            logger.warning(f"Reverse geocoding failed with status {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Reverse geocoding request failed: {e}")
        return None
