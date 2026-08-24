import os
import requests
import streamlit as st
import logging

logger = logging.getLogger(__name__)

@st.cache_data(show_spinner=False, ttl=3600)
def get_pexels_image(query: str) -> dict:
    """
    Searches Pexels API for a photo matching the query.
    Returns a normalized dictionary with image details.
    """
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    
    unavailable_response = {
        "title": query,
        "image_url": None,
        "photographer": None,
        "photo_url": None,
        "source": "Pexels",
        "source_type": "STOCK_PHOTO",
        "available": False
    }

    if not api_key:
        logger.warning("PEXELS_API_KEY is not set.")
        return unavailable_response

    search_url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": api_key
    }
    params = {
        "query": query,
        "per_page": 1
    }

    try:
        res = requests.get(search_url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()

        if data.get("photos") and len(data["photos"]) > 0:
            photo = data["photos"][0]
            return {
                "title": query,
                "image_url": photo["src"]["medium"],  # medium is usually a good size for UI
                "photographer": photo.get("photographer", "Unknown Photographer"),
                "photo_url": photo.get("url"),
                "source": "Pexels",
                "source_type": "STOCK_PHOTO",
                "available": True
            }

    except requests.exceptions.HTTPError as e:
        logger.error(f"Pexels API HTTP Error for '{query}': {e}")
    except Exception as e:
        logger.error(f"Error fetching Pexels image for '{query}': {e}")

    return unavailable_response
