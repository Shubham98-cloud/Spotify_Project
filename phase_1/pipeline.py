import os
import json
import argparse
import logging
from datetime import datetime, timedelta, timezone

from ingest_app_store import fetch_app_store_reviews
from ingest_play_store import fetch_play_store_reviews
from ingest_reddit import fetch_reddit_reviews
from cleaner import clean_and_enrich_review

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pipeline")

def run_pipeline(limit: int, skip_app_store: bool, skip_play_store: bool, skip_reddit: bool, output_dir: str):
    """
    Orchestrates the ingestion and cleaning/ETL pipeline for Phase 1.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    
    all_raw_reviews = []
    
    # 1. Fetch Apple App Store reviews
    if not skip_app_store:
        try:
            # RSS pagination limits: 1 page is ~50 reviews.
            pages = max(1, limit // 50)
            app_store_raw = fetch_app_store_reviews(page_limit=pages)
            # Limit exactly to requested count if we fetched more
            all_raw_reviews.extend(app_store_raw[:limit])
        except Exception as e:
            logger.error(f"Failed App Store ingestion: {e}")
            
    # 2. Fetch Google Play Store reviews
    if not skip_play_store:
        try:
            play_store_raw = fetch_play_store_reviews(count=limit)
            all_raw_reviews.extend(play_store_raw)
        except Exception as e:
            logger.error(f"Failed Play Store Ingestion: {e}")
            
    # 3. Fetch Reddit discussions
    if not skip_reddit:
        try:
            reddit_raw = fetch_reddit_reviews(limit=limit)
            all_raw_reviews.extend(reddit_raw)
        except Exception as e:
            logger.error(f"Failed Reddit Ingestion: {e}")
            
    total_raw_count = len(all_raw_reviews)
    logger.info(f"Total raw reviews ingested: {total_raw_count}")
    
    if total_raw_count == 0:
        logger.warning("No reviews were ingested. Exiting pipeline.")
        return
    
    # Save Raw data
    raw_output_path = os.path.join(output_dir, f"raw_ingested_{timestamp}.json")
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump(all_raw_reviews, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved raw ingested data to: {raw_output_path}")
    
    # 4. Cleaning & ETL Enrichment
    logger.info("Starting cleaning and metadata enrichment pipeline...")
    cleaned_reviews = []
    source_stats = {"app_store": 0, "play_store": 0, "reddit": 0}
    segment_stats = {}
    
    # Pre-parse and find the latest date for App Store reviews to account for RSS feed delays
    app_store_dates = []
    for raw in all_raw_reviews:
        if raw.get("source") == "app_store":
            d_str = raw.get("date", "")
            if d_str:
                try:
                    clean_d = d_str.replace("Z", "+00:00")
                    dt_val = datetime.fromisoformat(clean_d)
                    if dt_val.tzinfo is None:
                        dt_val = dt_val.replace(tzinfo=timezone.utc)
                    app_store_dates.append(dt_val)
                except:
                    pass
    latest_app_store_date = max(app_store_dates) if app_store_dates else datetime.now(timezone.utc)
    if latest_app_store_date.tzinfo is None:
        latest_app_store_date = latest_app_store_date.replace(tzinfo=timezone.utc)
    
    for raw in all_raw_reviews:
        try:
            cleaned = clean_and_enrich_review(raw)
            if cleaned is None:
                continue
            
            # Filter: only keep reviews from the past 24 hours
            date_str = cleaned.get("date", "")
            if date_str:
                try:
                    # Parse standard ISO string like '2026-06-27T00:12:34.567Z'
                    clean_date_str = date_str.replace("Z", "+00:00")
                    review_dt = datetime.fromisoformat(clean_date_str)
                    
                    # Ensure review_dt is timezone-aware
                    if review_dt.tzinfo is None:
                        review_dt = review_dt.replace(tzinfo=timezone.utc)
                    
                    # For app_store, compare against the latest available date in the RSS feed
                    if cleaned.get("source") == "app_store":
                        time_diff = latest_app_store_date - review_dt
                    else:
                        time_diff = datetime.now(timezone.utc) - review_dt
                        
                    if time_diff.total_seconds() > 24 * 3600 or time_diff.total_seconds() < 0:
                        continue  # Skip reviews outside the 24-hour window
                except Exception as ex:
                    logger.debug(f"Failed parsing date {date_str} for 24h filter: {ex}")
            
            cleaned_reviews.append(cleaned)
            
            # Keep stats
            source = cleaned.get("source", "unknown")
            source_stats[source] = source_stats.get(source, 0) + 1
            
            for segment in cleaned.get("inferred_segments", []):
                segment_stats[segment] = segment_stats.get(segment, 0) + 1
        except Exception as e:
            logger.error(f"Failed processing review {raw.get('review_id', 'unknown')}: {e}")
            
    # Save Cleaned data
    cleaned_output_path = os.path.join(output_dir, f"cleaned_reviews_{timestamp}.json")
    with open(cleaned_output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_reviews, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cleaned and enriched data to: {cleaned_output_path}")
    
    # 5. Output Run Summary Table
    print("\n" + "="*50)
    print("           PHASE 1 RUN PIPELINE SUMMARY")
    print("="*50)
    print(f"Timestamp:       {timestamp} UTC")
    print(f"Total Ingested:  {total_raw_count}")
    print(f"Total Cleaned:   {len(cleaned_reviews)}")
    print("-"*50)
    print("Ingestion Source Breakdown:")
    for src, count in source_stats.items():
        print(f" - {src:<12}: {count}")
    print("-"*50)
    print("Inferred User Segment / Issue Breakdown:")
    for segment, count in segment_stats.items():
        print(f" - {segment:<28}: {count}")
    print("="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1: Ingestion & ETL Pipeline Orchestrator")
    parser.add_argument("--limit", type=int, default=50, help="Max number of items to fetch per source (default: 50)")
    parser.add_argument("--skip-appstore", action="store_true", help="Skip Apple App Store ingestion")
    parser.add_argument("--skip-playstore", action="store_true", help="Skip Google Play Store ingestion")
    parser.add_argument("--skip-reddit", action="store_true", help="Skip Reddit discussions ingestion")
    parser.add_argument("--output-dir", type=str, default="Data", help="Directory to save JSON files (default: Data)")
    
    args = parser.parse_args()
    
    # Resolve absolute path for output dir. Default to workspace root's 'Data' folder.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(base_dir)
    if not os.path.isabs(args.output_dir):
        # Resolve relative to workspace root, mapping 'data' to 'Data'
        folder_name = "Data" if args.output_dir.lower() == "data" else args.output_dir
        target_output_dir = os.path.join(workspace_root, folder_name)
    else:
        target_output_dir = args.output_dir
    
    run_pipeline(
        limit=args.limit,
        skip_app_store=args.skip_appstore,
        skip_play_store=args.skip_playstore,
        skip_reddit=args.skip_reddit,
        output_dir=target_output_dir
    )
