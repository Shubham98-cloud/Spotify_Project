import os
import sys
import json
import logging
from datetime import datetime

# Add workspace root and phase_2 to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from stream_adapter import stream_live_reviews
except ModuleNotFoundError:
    from phase_3.stream_adapter import stream_live_reviews

from phase_2.embedder import get_embeddings
from phase_2.clustering import cluster_reviews
from phase_2.llm_synthesizer import synthesize_cluster

logger = logging.getLogger("phase_3_pipeline")

def run_realtime_pipeline(timeframe: str = "7d", limit_per_source: int = 50, min_cluster_size: int = 2, output_dir: str = None) -> list:
    """
    Orchestrates the dynamic scraping, filtering, clustering, and synthesis process.
    Everything runs dynamically in-memory without database storage.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    if output_dir is None:
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(workspace_root, "Data")
    elif not os.path.isabs(output_dir):
        # Resolve relative path relative to workspace root
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder_name = "Data" if output_dir.lower() == "data" else output_dir
        output_dir = os.path.join(workspace_root, folder_name)
            
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Starting real-time streaming pipeline (timeframe={timeframe}, limit={limit_per_source})...")

    # 1. Fetch filtered reviews dynamically
    reviews = list(stream_live_reviews(timeframe=timeframe, limit_per_source=limit_per_source))
    n_reviews = len(reviews)
    logger.info(f"Loaded {n_reviews} reviews from stream.")
    
    if n_reviews == 0:
        logger.warning("No reviews found in this timeframe. Exiting.")
        return []

    # 2. Extract and filter content text — use `or ''` to guard against None content fields
    texts = [(r.get("content") or "").strip() for r in reviews]
    valid_indices = [i for i, t in enumerate(texts) if len(t) > 3]
    filtered_texts = [texts[i] for i in valid_indices]
    filtered_reviews = [reviews[i] for i in valid_indices]

    if not filtered_texts:
        logger.warning("No valid text contents found to cluster.")
        return []

    # 3. Vectorization (Embeddings)
    embeddings = get_embeddings(filtered_texts)

    # 4. Clustering (PCA + HDBSCAN)
    cluster_labels = cluster_reviews(embeddings, min_cluster_size=min_cluster_size)

    # Group reviews by cluster label
    clusters = {}
    for idx, label in enumerate(cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(filtered_reviews[idx])

    # 5. LLM Theme Synthesis
    final_report = []
    sorted_cluster_labels = sorted([l for l in clusters.keys() if l != -1])

    logger.info(f"Synthesizing {len(sorted_cluster_labels)} emergent clusters...")
    for label in sorted_cluster_labels:
        cluster_list = clusters[label]
        logger.info(f"Synthesizing Cluster {label} ({len(cluster_list)} reviews)...")
        summary = synthesize_cluster(cluster_list)

        final_report.append({
            "cluster_id": label,
            "theme_name": summary["theme_name"],
            "action_idea": summary["action_idea"],
            "representative_quotes": summary["representative_quotes"],
            "size": len(cluster_list),
            "reviews": cluster_list
        })

    # Group noise / unclustered
    noise_list = clusters.get(-1, [])
    if noise_list:
        final_report.append({
            "cluster_id": -1,
            "theme_name": "Unclustered General Feedback",
            "action_idea": "Monitor for new emerging themes as feedback grows.",
            "representative_quotes": [(r.get("content") or "")[:200] for r in noise_list[:3]],
            "size": len(noise_list),
            "reviews": noise_list
        })

    # 6. Save results
    output_path = os.path.join(output_dir, f"realtime_clusters_{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved real-time cluster results to: {output_path}")

    return final_report

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_realtime_pipeline(timeframe="30d", limit_per_source=5)
