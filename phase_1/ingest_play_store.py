import logging
import json
from datetime import datetime
from google_play_scraper import Sort, reviews

logger = logging.getLogger(__name__)

SPOTIFY_PACKAGE_NAME = "com.spotify.music"

def fetch_play_store_reviews(package_name: str = SPOTIFY_PACKAGE_NAME, count: int = 100, countries: list = None) -> list:
    """
    Fetches reviews for Spotify from Google Play Store using the google-play-scraper library across multiple countries.
    """
    if countries is None:
        countries = ["us", "in", "gb", "ca", "au"]

    reviews_list = []
    seen_ids = set()

    # Distribute the count across countries
    count_per_country = max(1, count // len(countries))

    for country in countries:
        try:
            logger.info(f"Fetching Google Play reviews for {package_name} in country {country.upper()} (count={count_per_country})...")
            # We sort by newest to get fresh feedback
            result, _ = reviews(
                package_name,
                lang='en',
                country=country,
                sort=Sort.NEWEST,
                count=count_per_country
            )
            
            for r in result:
                try:
                    review_id = r.get("reviewId", "")
                    if not review_id or review_id in seen_ids:
                        continue
                    
                    content = r.get("content") or ""
                    
                    # Skip reviews with no text content
                    if not content.strip():
                        continue
                    
                    # Format date to ISO string
                    date_val = r.get("at")
                    if isinstance(date_val, datetime):
                        iso_date = date_val.isoformat() + "Z"
                    elif date_val:
                        iso_date = str(date_val)
                    else:
                        iso_date = datetime.utcnow().isoformat() + "Z"
                    
                    app_version = r.get("reviewCreatedVersion", "")
                    
                    seen_ids.add(review_id)
                    reviews_list.append({
                        "review_id": review_id,
                        "source": "play_store",
                        "author": r.get("userName", "Anonymous"),
                        "title": "", # Play Store reviews do not have titles
                        "content": content,
                        "rating": int(r.get("score", 0)),
                        "date": iso_date,
                        "app_version": app_version or ""
                    })
                except Exception as e:
                    logger.error(f"Error parsing Google Play review in country {country.upper()}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching Google Play Store reviews in country {country.upper()}: {e}")
            
    logger.info(f"Successfully fetched {len(reviews_list)} Google Play reviews across countries: {', '.join([c.upper() for c in countries])}.")
    return reviews_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reviews_data = fetch_play_store_reviews(count=10, countries=["us", "in"])
    print(f"Sample review: {json.dumps(reviews_data[0] if reviews_data else {}, indent=2)}")
