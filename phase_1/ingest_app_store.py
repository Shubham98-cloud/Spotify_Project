import requests
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SPOTIFY_APP_STORE_ID = "324684580"

def fetch_app_store_reviews(app_id: str = SPOTIFY_APP_STORE_ID, page_limit: int = 5, countries: list = None) -> list:
    """
    Fetches recent reviews for Spotify from the Apple App Store RSS feed across multiple countries.
    """
    if countries is None:
        countries = ["us", "in", "gb", "ca", "au"]

    reviews_list = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    seen_ids = set()

    for country in countries:
        for page in range(1, page_limit + 1):
            # We fetch the JSON RSS feed
            url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
            try:
                logger.info(f"Fetching App Store reviews page {page} for country {country.upper()} from RSS...")
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch App Store reviews page {page} for country {country.upper()}. Status code: {response.status_code}")
                    break
                
                data = response.json()
                feed = data.get("feed", {})
                entries = feed.get("entry", [])
                
                # If there's only 1 entry, it might be a dictionary rather than a list. Let's make sure it's a list.
                if isinstance(entries, dict):
                    entries = [entries]
                
                if not entries:
                    logger.info(f"No reviews found on page {page} for country {country.upper()}.")
                    break
                    
                for entry in entries:
                    # The first entry in iTunes JSON is typically the app info/author, not a review.
                    # Let's skip it if it doesn't have an ID or is missing 'im:rating'
                    if "im:rating" not in entry:
                        continue
                    
                    try:
                        review_id = entry.get("id", {}).get("label", "")
                        if not review_id or review_id in seen_ids:
                            continue
                        
                        author = entry.get("author", {}).get("name", {}).get("label", "Anonymous")
                        title = entry.get("title", {}).get("label", "")
                        content = entry.get("content", {}).get("label", "")
                        rating = int(entry.get("im:rating", {}).get("label", 0))
                        app_version = entry.get("im:version", {}).get("label", "")
                        
                        # Feed doesn't always have exact ISO date in a simple field. Let's try to extract updated/date.
                        # Usually there's an 'updated' field or we fallback to current time
                        date_str = entry.get("updated", {}).get("label", "")
                        if date_str:
                            # Format is like '2026-06-20T12:00:00-07:00'
                            try:
                                date_obj = datetime.fromisoformat(date_str)
                                iso_date = date_obj.isoformat()
                            except ValueError:
                                iso_date = date_str
                        else:
                            iso_date = datetime.utcnow().isoformat() + "Z"

                        seen_ids.add(review_id)
                        reviews_list.append({
                            "review_id": review_id,
                            "source": "app_store",
                            "author": author,
                            "title": title,
                            "content": content,
                            "rating": rating,
                            "date": iso_date,
                            "app_version": app_version
                        })
                    except Exception as e:
                        logger.error(f"Error parsing App Store review entry: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error fetching App Store reviews page {page} for country {country.upper()}: {e}")
                break
                
    logger.info(f"Successfully fetched {len(reviews_list)} App Store reviews across countries: {', '.join([c.upper() for c in countries])}.")
    return reviews_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reviews = fetch_app_store_reviews(page_limit=2, countries=["us", "in"])
    print(f"Sample review: {json.dumps(reviews[0] if reviews else {}, indent=2)}")
