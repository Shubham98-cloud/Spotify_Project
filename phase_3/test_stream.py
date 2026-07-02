import logging
from datetime import datetime, timedelta, timezone
from stream_adapter import parse_timeframe, parse_iso_date, stream_live_reviews

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_stream")

# Test Mock Data with varying timestamps
NOW_UTC = datetime.now(timezone.utc)
MOCK_STREAM_REVIEWS = [
    {"review_id": "t1", "source": "test", "content": "Widget issues on home screen", "date": (NOW_UTC - timedelta(hours=5)).isoformat()},      # 5h ago
    {"review_id": "t2", "source": "test", "content": "Shuffle loop is boring", "date": (NOW_UTC - timedelta(days=3)).isoformat()},          # 3d ago
    {"review_id": "t3", "source": "test", "content": "App freezes on start", "date": (NOW_UTC - timedelta(days=15)).isoformat()},          # 15d ago
    {"review_id": "t4", "source": "test", "content": "Love the UI layout updates", "date": (NOW_UTC - timedelta(days=45)).isoformat()}      # 45d ago
]

def test_timeframe_parsing():
    logger.info("Checking timeframe parser...")
    assert parse_timeframe("24h") == timedelta(hours=24)
    assert parse_timeframe("7d") == timedelta(days=7)
    assert parse_timeframe("30d") == timedelta(days=30)
    assert parse_timeframe("invalid") == timedelta(days=7) # fallback default
    logger.info("✓ Timeframe parsing checked.")

def test_date_cutoff_filtering():
    logger.info("Checking date filtering logic...")
    
    # 24h filter
    delta_24h = parse_timeframe("24h")
    cutoff_24h = NOW_UTC - delta_24h
    filtered_24h = [r for r in MOCK_STREAM_REVIEWS if parse_iso_date(r["date"]) >= cutoff_24h]
    assert len(filtered_24h) == 1, f"Expected 1 review, found {len(filtered_24h)}"
    assert filtered_24h[0]["review_id"] == "t1"

    # 7d filter
    delta_7d = parse_timeframe("7d")
    cutoff_7d = NOW_UTC - delta_7d
    filtered_7d = [r for r in MOCK_STREAM_REVIEWS if parse_iso_date(r["date"]) >= cutoff_7d]
    assert len(filtered_7d) == 2, f"Expected 2 reviews, found {len(filtered_7d)}"
    assert {r["review_id"] for r in filtered_7d} == {"t1", "t2"}

    # 30d filter
    delta_30d = parse_timeframe("30d")
    cutoff_30d = NOW_UTC - delta_30d
    filtered_30d = [r for r in MOCK_STREAM_REVIEWS if parse_iso_date(r["date"]) >= cutoff_30d]
    assert len(filtered_30d) == 3, f"Expected 3 reviews, found {len(filtered_30d)}"
    assert {r["review_id"] for r in filtered_30d} == {"t1", "t2", "t3"}

    logger.info("✓ Cutoff filtering checked.")

def run_all_checks():
    logger.info("Starting Phase 3 verification test...")
    test_timeframe_parsing()
    test_date_cutoff_filtering()
    logger.info("=" * 60)
    logger.info("  ALL PHASE 3 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_all_checks()
