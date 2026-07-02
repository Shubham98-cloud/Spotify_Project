import os
import sys
import logging
from datetime import datetime, timedelta, timezone

# Add workspace root to sys.path to allow importing phase_1 modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase_1.ingest_app_store import fetch_app_store_reviews
from phase_1.ingest_play_store import fetch_play_store_reviews
from phase_1.ingest_reddit import fetch_reddit_reviews
from phase_1.cleaner import clean_and_enrich_review

logger = logging.getLogger(__name__)

def parse_timeframe(timeframe_str: str) -> timedelta:
    """
    Parses timeframe strings like '24h', '7d', '30d' into a timedelta object.
    Defaults to 7 days if parsing fails.
    """
    timeframe_str = timeframe_str.lower().strip()
    if timeframe_str.endswith("h"):
        try:
            hours = int(timeframe_str[:-1])
            return timedelta(hours=hours)
        except ValueError:
            pass
    elif timeframe_str.endswith("d"):
        try:
            days = int(timeframe_str[:-1])
            return timedelta(days=days)
        except ValueError:
            pass
            
    # Default to 7 days
    logger.warning(f"Unknown timeframe format '{timeframe_str}'. Defaulting to '7d'.")
    return timedelta(days=7)

def parse_iso_date(date_str: str) -> datetime:
    """
    Safely parses an ISO date string into a timezone-aware UTC datetime.
    Handles 'Z' suffix and numeric timezone offsets.
    """
    if not date_str:
        return datetime.now(timezone.utc)
        
    # Standardize 'Z' to '+00:00' for fromisoformat compatibility
    date_str = date_str.strip()
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
        
    try:
        # datetime.fromisoformat handles offsets like -07:00 or +00:00
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        logger.debug(f"Failed to parse date '{date_str}': {e}. Using current time.")
        return datetime.now(timezone.utc)

def stream_live_reviews(timeframe: str = "7d", limit_per_source: int = 250):
    """
    Exposes an in-memory stream generator (ETL Buffer).
    Scrapes reviews in real-time, filters them on-the-fly by date,
    cleans them, and yields them one-by-one.
    """
    delta = parse_timeframe(timeframe)
    cutoff_time = datetime.now(timezone.utc) - delta
    
    logger.info(f"Streaming reviews newer than cutoff: {cutoff_time.isoformat()}")
    
    # 1. Stream App Store Reviews
    logger.info("Accessing App Store stream...")
    app_store_count = 0
    try:
        # Apple RSS paginates at ~50 reviews/page, max 10 pages (500 reviews total)
        pages = max(1, min(limit_per_source // 50, 10))
        # Fetch raw reviews
        raw_app_reviews = fetch_app_store_reviews(page_limit=pages)
        for raw in raw_app_reviews:
            if app_store_count >= limit_per_source:
                break
                
            review_date = parse_iso_date(raw.get("date"))
            if review_date >= cutoff_time:
                cleaned = clean_and_enrich_review(raw)
                if cleaned is None:
                    continue
                app_store_count += 1
                yield cleaned
    except Exception as e:
        logger.error(f"Error streaming App Store reviews: {e}")

    # 2. Stream Play Store Reviews
    logger.info("Accessing Play Store stream...")
    play_store_count = 0
    try:
        # Fetch slightly more than limit to account for timeframe filter dropouts
        fetch_count = max(limit_per_source, int(limit_per_source * 1.3))
        raw_play_reviews = fetch_play_store_reviews(count=fetch_count)
        for raw in raw_play_reviews:
            if play_store_count >= limit_per_source:
                break
                
            review_date = parse_iso_date(raw.get("date"))
            if review_date >= cutoff_time:
                cleaned = clean_and_enrich_review(raw)
                if cleaned is None:
                    continue
                play_store_count += 1
                yield cleaned
    except Exception as e:
        logger.error(f"Error streaming Play Store reviews: {e}")

    # 3. Stream Reddit Posts
    logger.info("Accessing Reddit stream...")
    reddit_count = 0
    try:
        # Fetch raw discussions
        raw_reddit = fetch_reddit_reviews(limit=limit_per_source * 2)
        for raw in raw_reddit:
            if reddit_count >= limit_per_source:
                break
                
            post_date = parse_iso_date(raw.get("date"))
            if post_date >= cutoff_time:
                cleaned = clean_and_enrich_review(raw)
                if cleaned is None:
                    continue
                reddit_count += 1
                yield cleaned
    except Exception as e:
        logger.error(f"Error streaming Reddit reviews: {e}")

    logger.info(f"Dynamic streaming complete. Emitted: App Store ({app_store_count}), Play Store ({play_store_count}), Reddit ({reddit_count}).")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test streaming past 30 days, limit 2
    logger.info("Testing Stream Generator...")
    stream = stream_live_reviews(timeframe="30d", limit_per_source=2)
    for review in stream:
        print(f"[{review['source'].upper()}] Rating: {review['rating']} - Date: {review['date']}")
        print(f"Content: {review['content'][:80]}...")
