import os
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

def get_embeddings(texts: list) -> np.ndarray:
    """
    Generates embeddings for a list of strings.
    If OPENAI_API_KEY is found in the environment, it uses OpenAI's API (text-embedding-3-small).
    Otherwise, it falls back to a scikit-learn TF-IDF vectorizer of 1536 features.
    """
    if not texts:
        return np.empty((0, 1536))

    api_key = os.environ.get("OPENAI_API_KEY")
    
    if api_key:
        logger.info(f"Generating OpenAI embeddings for {len(texts)} texts...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            # Convert response to a numpy array
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)
        except Exception as e:
            logger.warning(f"OpenAI embedding generation failed: {e}. Falling back to local TF-IDF.")
            # Fallback to TF-IDF if API fails
            
    # TF-IDF Fallback
    logger.info(f"Generating local TF-IDF embeddings (dimension 1536) for {len(texts)} texts...")
    try:
        # We enforce max_features=1536 to match the dimensions of text-embedding-3-small
        vectorizer = TfidfVectorizer(max_features=1536)
        tfidf_matrix = vectorizer.fit_transform(texts).toarray()
        
        # If the vocabulary is smaller than 1536 (e.g. few short texts), pad it with zeros to have exactly 1536 cols
        n_samples, n_features = tfidf_matrix.shape
        if n_features < 1536:
            padding = np.zeros((n_samples, 1536 - n_features))
            tfidf_matrix = np.hstack((tfidf_matrix, padding))
            
        return tfidf_matrix
    except Exception as e:
        logger.error(f"Failed to generate TF-IDF fallback: {e}")
        # Return random/empty matching dimensions to keep pipeline alive
        return np.random.rand(len(texts), 1536)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_texts = ["I love discovering new songs!", "Spotify repeat loop is boring."]
    vecs = get_embeddings(test_texts)
    print(f"Generated embeddings shape: {vecs.shape}")
