import os
import json
import logging
from embedder import get_embeddings
from clustering import cluster_reviews
from llm_synthesizer import synthesize_cluster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_clustering")

MOCK_REVIEWS = [
    # Cluster A: Recommendation loop fatigue
    {"review_id": "mock_a1", "source": "test", "content": "I keep hearing the same songs on my shuffle. The repeat loop is so boring."},
    {"review_id": "mock_a2", "source": "test", "content": "Why is the loop repeating the same songs? Spotify is boring now."},
    {"review_id": "mock_a3", "source": "test", "content": "Shuffle recommendations are stuck in a repeat loop, it keeps playing the same music."},
    
    # Cluster B: UI Widget issues
    {"review_id": "mock_b1", "source": "test", "content": "I hate the new interface, where did my widget go? Bring back the widget."},
    {"review_id": "mock_b2", "source": "test", "content": "Give me back my screen widget, the new layout and widget removal is bad."},
    {"review_id": "mock_b3", "source": "test", "content": "The home screen widget was removed in the latest layout update. Bring it back."},
    
    # Cluster C: Performance stability
    {"review_id": "mock_c1", "source": "test", "content": "App crashes on launch, it is so buggy and laggy."},
    {"review_id": "mock_c2", "source": "test", "content": "Spotify keeps freezing and crashes when playing music offline."}
]

def run_verification_test():
    logger.info("Starting verification test with mock data...")
    
    texts = [r["content"] for r in MOCK_REVIEWS]
    
    # 1. Test embedding generation
    embeddings = get_embeddings(texts)
    assert embeddings.shape == (len(MOCK_REVIEWS), 1536), f"Expected shape (8, 1536), got {embeddings.shape}"
    logger.info("✓ Embeddings generation checked successfully.")
    
    # 2. Test clustering
    labels = cluster_reviews(embeddings, min_cluster_size=2)
    assert len(labels) == len(MOCK_REVIEWS), "Labels size mismatch"
    logger.info(f"Generated cluster labels: {labels}")
    
    unique_labels = set(labels) - {-1}
    assert len(unique_labels) >= 2, f"Expected at least 2 clusters, found {len(unique_labels)}"
    logger.info("✓ Clustering checked successfully.")
    
    # Group reviews by cluster
    clusters = {}
    for idx, l in enumerate(labels):
        if l not in clusters:
            clusters[l] = []
        clusters[l].append(MOCK_REVIEWS[idx])
        
    # 3. Test LLM / Heuristic synthesis & quote constraints
    logger.info("Running synthesis checks...")
    for label in unique_labels:
        cluster_list = clusters[label]
        summary = synthesize_cluster(cluster_list)
        
        # Verify theme name length <= 6 words
        name_words = len(summary["theme_name"].split())
        logger.info(f"Theme Name: '{summary['theme_name']}' ({name_words} words)")
        assert name_words <= 6, f"Theme Name exceeds 6 words: '{summary['theme_name']}'"
        
        # Verify action idea length <= 25 words
        action_words = len(summary["action_idea"].split())
        logger.info(f"Action Idea: '{summary['action_idea']}' ({action_words} words)")
        assert action_words <= 25, f"Action Idea exceeds 25 words: '{summary['action_idea']}'"
        
        # Verify verbatim quotes exist in source reviews
        for quote in summary["representative_quotes"]:
            logger.info(f"Quote: '{quote}'")
            matched = False
            for r in cluster_list:
                if quote.lower() in r["content"].lower():
                    matched = True
                    break
            assert matched, f"Quote '{quote}' does not exist verbatim in cluster reviews."
            
    logger.info("✓ Synthesis and constraints checked successfully.")
    logger.info("=" * 60)
    logger.info("  ALL PHASE 2 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_verification_test()
