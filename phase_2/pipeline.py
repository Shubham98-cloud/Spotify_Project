import os
import sys
import json
import argparse
import logging
from datetime import datetime

# Reconfigure stdout and stderr to UTF-8 to prevent encoding crashes on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add workspace root to sys.path to allow importing phase_1 modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from embedder import get_embeddings
from clustering import cluster_reviews
from llm_synthesizer import synthesize_cluster

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("phase_2_pipeline")

def get_latest_cleaned_file() -> str:
    """
    Scans the workspace root 'Data/' directory for the most recent cleaned reviews JSON file.
    """
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p1_data_dir = os.path.join(workspace_root, "Data")
    if not os.path.exists(p1_data_dir):
        # Fallback to check phase_1/data/
        p1_data_dir = os.path.join(workspace_root, "phase_1", "data")
        if not os.path.exists(p1_data_dir):
            return None
        
    cleaned_files = [
        os.path.join(p1_data_dir, f) for f in os.listdir(p1_data_dir)
        if f.startswith("cleaned_reviews_") and f.endswith(".json")
    ]
    if not cleaned_files:
        return None
        
    # Sort by filename timestamp (newest first)
    cleaned_files.sort(reverse=True)
    return cleaned_files[0]

def scrape_and_clean_realtime(limit: int) -> list:
    """
    Dynamically imports Phase 1 scraper and cleaning modules to ingest
    and process reviews on-the-fly.
    """
    logger.info("Executing real-time scrape from App Store, Play Store, and Reddit...")
    
    from phase_1.ingest_app_store import fetch_app_store_reviews
    from phase_1.ingest_play_store import fetch_play_store_reviews
    from phase_1.ingest_reddit import fetch_reddit_reviews
    from phase_1.cleaner import clean_and_enrich_review
    
    raw_reviews = []
    
    # 1. Fetch from App Store
    try:
        pages = max(1, limit // 50)
        app_reviews = fetch_app_store_reviews(page_limit=pages)
        raw_reviews.extend(app_reviews[:limit])
    except Exception as e:
        logger.error(f"Real-time App Store fetch failed: {e}")
        
    # 2. Fetch from Play Store
    try:
        play_reviews = fetch_play_store_reviews(count=limit)
        raw_reviews.extend(play_reviews)
    except Exception as e:
        logger.error(f"Real-time Play Store fetch failed: {e}")
        
    # 3. Fetch from Reddit
    try:
        reddit_reviews = fetch_reddit_reviews(limit=limit)
        raw_reviews.extend(reddit_reviews)
    except Exception as e:
        logger.error(f"Real-time Reddit fetch failed: {e}")
        
    logger.info(f"Scraped {len(raw_reviews)} raw reviews. Processing cleaning and ETL...")
    
    cleaned_reviews = []
    for r in raw_reviews:
        try:
            cleaned = clean_and_enrich_review(r)
            cleaned_reviews.append(cleaned)
        except Exception as e:
            logger.error(f"ETL cleaning failed for review {r.get('review_id')}: {e}")
            
    logger.info(f"Completed dynamic ETL. {len(cleaned_reviews)} reviews loaded in-memory.")
    return cleaned_reviews

def run_analytics_pipeline(realtime: bool, input_file: str, limit: int, min_cluster_size: int, output_dir: str):
    """
    Orchestrates the AI embedding, HDBSCAN clustering, and LLM synthesis.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Get Cleaned Reviews Dataset
    reviews = []
    if realtime:
        reviews = scrape_and_clean_realtime(limit=limit)
    else:
        # Load from file
        target_file = input_file or get_latest_cleaned_file()
        if not target_file:
            logger.error("No input file found, and --realtime was not specified. Run Phase 1 first or use --realtime.")
            sys.exit(1)
        logger.info(f"Loading cleaned reviews from: {target_file}")
        with open(target_file, "r", encoding="utf-8") as f:
            reviews = json.load(f)
            
    n_reviews = len(reviews)
    logger.info(f"Loaded {n_reviews} reviews for clustering.")
    if n_reviews == 0:
        logger.error("No reviews available for clustering. Exiting.")
        return
        
    # Extract contents for embedding
    texts = [r.get("content", "").strip() for r in reviews]
    # Filter out empty texts
    valid_indices = [i for i, t in enumerate(texts) if len(t) > 3]
    filtered_texts = [texts[i] for i in valid_indices]
    filtered_reviews = [reviews[i] for i in valid_indices]
    
    if not filtered_texts:
        logger.error("No valid text reviews found to embed. Exiting.")
        return
        
    # 2. Vectorization
    embeddings = get_embeddings(filtered_texts)
    
    # 3. Clustering
    cluster_labels = cluster_reviews(embeddings, min_cluster_size=min_cluster_size)
    
    # Group reviews by cluster
    clusters = {}
    for idx, label in enumerate(cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(filtered_reviews[idx])
        
    # 4. LLM Synthesis & Reasoning
    final_clusters_report = []
    
    # Process regular clusters (excluding noise label -1)
    sorted_cluster_labels = sorted([l for l in clusters.keys() if l != -1])
    
    logger.info(f"Starting LLM/heuristic synthesis on {len(sorted_cluster_labels)} clusters...")
    for label in sorted_cluster_labels:
        cluster_list = clusters[label]
        logger.info(f"Synthesizing Cluster {label} ({len(cluster_list)} reviews)...")
        summary = synthesize_cluster(cluster_list)
        
        final_clusters_report.append({
            "cluster_id": label,
            "theme_name": summary["theme_name"],
            "action_idea": summary["action_idea"],
            "representative_quotes": summary["representative_quotes"],
            "size": len(cluster_list),
            "reviews": cluster_list
        })
        
    # Handle noise (unclustered reviews)
    noise_list = clusters.get(-1, [])
    if noise_list:
        final_clusters_report.append({
            "cluster_id": -1,
            "theme_name": "Unclustered General Feedback",
            "action_idea": "Monitor for new emerging themes as feedback grows.",
            "representative_quotes": [r.get("content", "")[:100] for r in noise_list[:2]],
            "size": len(noise_list),
            "reviews": noise_list
        })
        
    # 5. Save Output
    output_path = os.path.join(output_dir, f"cluster_results_{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_clusters_report, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved analytics cluster results to: {output_path}")
    
    # 6. Print Summary
    print("\n" + "="*60)
    print("           PHASE 2 ANALYTICS PIPELINE RESULTS")
    print("="*60)
    print(f"Timestamp:          {timestamp} UTC")
    print(f"Total Reviews:      {n_reviews}")
    print(f"Clustered Groups:   {len(sorted_cluster_labels)}")
    print("-"*60)
    
    for c in final_clusters_report:
        if c["cluster_id"] == -1:
            continue
        print(f"Cluster #{c['cluster_id']} ({c['size']} reviews):")
        print(f"  Theme Name : {c['theme_name'].upper()}")
        print(f"  Action Idea: {c['action_idea']}")
        print(f"  Quotes     :")
        for q in c["representative_quotes"]:
            print(f"    - \"{q}\"")
        print("-"*60)
        
    if noise_list:
        print(f"Unclustered Noise: {len(noise_list)} reviews")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: Analytics & Clustering Pipeline")
    parser.add_argument("--realtime", action="store_true", help="Scrape data in real-time from store APIs instead of static files")
    parser.add_argument("--limit", type=int, default=50, help="Max reviews to scrape per source in --realtime mode (default: 50)")
    parser.add_argument("--input-file", type=str, default=None, help="Path to input cleaned JSON file (defaults to newest in Data/)")
    parser.add_argument("--min-cluster-size", type=int, default=2, help="Minimum cluster size for HDBSCAN (default: 2)")
    parser.add_argument("--output-dir", type=str, default="Data", help="Directory to save output analytics JSON (default: Data)")
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(base_dir)
    if not os.path.isabs(args.output_dir):
        # Resolve relative to workspace root, mapping 'data' to 'Data'
        folder_name = "Data" if args.output_dir.lower() == "data" else args.output_dir
        target_output_dir = os.path.join(workspace_root, folder_name)
    else:
        target_output_dir = args.output_dir
    
    run_analytics_pipeline(
        realtime=args.realtime,
        input_file=args.input_file,
        limit=args.limit,
        min_cluster_size=args.min_cluster_size,
        output_dir=target_output_dir
    )
