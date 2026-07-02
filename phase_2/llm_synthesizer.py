import os
import json
import logging

logger = logging.getLogger(__name__)

def verify_and_align_quote(proposed_quote: str, review_texts: list) -> str:
    """
    Checks if the proposed quote exists verbatim in any of the review texts.
    If yes, returns the exact cased substring from the matching review.
    If no, returns None.
    """
    proposed_cleaned = proposed_quote.strip('"\'  \t\n.?!')
    if not proposed_cleaned or len(proposed_cleaned) < 5:
        return None
        
    for text in review_texts:
        if not text:
            continue
        idx = text.lower().find(proposed_cleaned.lower())
        if idx != -1:
            # Return the exact casing from the original review text
            return text[idx:idx + len(proposed_cleaned)].strip()
            
    return None

def synthesize_cluster_llm(cluster_reviews: list, api_key: str) -> dict:
    """
    Calls OpenAI to summarize a cluster of reviews.
    """
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    review_texts = [(r.get("content") or "").strip() for r in cluster_reviews if (r.get("content") or "").strip()]
    bulleted_reviews = "\n".join([f"- {text}" for text in review_texts])
    
    prompt = f"""You are a Growth Product Manager at Spotify. 
Analyze the following Spotify user reviews which belong to the same feedback cluster.

REVIEWS:
{bulleted_reviews}

Provide your analysis in JSON format with the following keys:
1. "theme_name": A short descriptive name for this cluster (MAXIMUM 6 words).
2. "action_idea": A detailed, elaborative product experiment or feature recommendation (3-4 sentences covering: the feature idea, A/B experiment design, and success metric hypothesis).
3. "representative_quotes": A list of 2-3 quotes of feedback. Each quote MUST exist VERBATIM (exact character match, case-insensitive) in the review list above.

JSON Format:
{{
  "theme_name": "...",
  "action_idea": "...",
  "representative_quotes": ["...", "...", "..."]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional PM assistant. You output strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        result = json.loads(response.choices[0].message.content)
        
        # Verify and clean the quotes
        verified_quotes = []
        for q in result.get("representative_quotes", []):
            aligned = verify_and_align_quote(q, review_texts)
            if aligned:
                verified_quotes.append(aligned)
                
        # If LLM failed to provide verbatim quotes, pull some directly from reviews
        if not verified_quotes:
            verified_quotes = [review_texts[0].strip()]
            
        return {
            "theme_name": result.get("theme_name", "Feedback Cluster")[:50],
            "action_idea": result.get("action_idea", "Improve recommendation quality."),
            "representative_quotes": verified_quotes
        }
    except Exception as e:
        logger.error(f"LLM synthesis failed: {e}. Falling back to local synthesizer.")
        return None

def synthesize_cluster_local_fallback(cluster_reviews: list) -> dict:
    """
    A smart local fallback that analyzes clusters using heuristic rules
    if no OpenAI API keys are configured. Produces rich, elaborative PM
    recommendations with experiment designs and success metrics.
    """
    review_texts = [(r.get("content") or "").strip() for r in cluster_reviews if (r.get("content") or "").strip()]
    if not review_texts:
        return {
            "theme_name": "General Feedback",
            "action_idea": "Gather more reviews for detailed analysis.",
            "representative_quotes": []
        }
        
    # Heuristically determine theme name based on common keywords
    combined_text = " ".join(review_texts).lower()
    
    # Default theme for unmatched clusters
    theme_name = "User Experience Insights"
    action_idea = (
        "Launch a 'Voice of the User' bi-weekly synthesis session with cross-functional PMs and engineers. "
        "Segment these reviews by NPS tier (Promoters/Passives/Detractors) and feed the top 3 pain-points "
        "into the quarterly OKR refinement cycle. Hypothesis: structured user feedback loops improve feature "
        "prioritization accuracy by 30% and reduce churn-inducing friction within 2 sprints. "
        "Secondary Action: Build an internal 'Feedback Heatmap' that overlays review sentiment onto the product feature map — "
        "this makes it immediately visible which product areas generate disproportionate negative signal vs. volume of usage."
    )
    
    if any(w in combined_text for w in ["loop", "repeat", "same song", "shuffle", "boring", "same tracks", "over and over", "echo chamber"]):
        theme_name = "Recommendation Repeat Loop Fatigue"
        action_idea = (
            "🔄 Feature: Launch 'Discovery Mode' — a dedicated toggle in Now Playing that forces Spotify's algorithm to break the familiarity loop "
            "by serving content from artists outside the user's top-50 listened pool. "
            "A/B Experiment: Expose 20% of Premium users to a 'Taste Refresh' weekly prompt that resets their taste profile weights partially "
            "(not fully), blending 40% familiar + 60% novel content for 14 days — measure new artist stream rate and skip rate delta. "
            "PM Hypothesis: Users who interact with the Discovery Mode toggle will show a 25% uplift in new artist streams and a 15% reduction "
            "in skip rates on Discover Weekly within the first 4 weeks, proving that user-controlled novelty injection beats purely algorithmic decisions. "
            "Secondary Action: Introduce a visual 'Novelty Dial' on the Discover Weekly playlist header letting users self-select freshness level "
            "(Familiar → Balanced → Bold), creating an explicit personalization signal that feeds back into the recommendation model."
        )
    elif any(w in combined_text for w in ["ads", "free", "commercial", "advertisement", "sponsor"]):
        theme_name = "Free User Ad Frequency Frustration"
        action_idea = (
            "💡 Feature: Introduce 'Spotify Ad Tokens' — a gamified daily reward system where Free users earn ad-skip credits by completing "
            "micro-interactions (e.g., rating a song, adding to a playlist, or sharing a track with a friend). "
            "A/B Experiment: Test a 'Contextual Ad Pause' feature for a 10% sample of Free users, reducing ad frequency during identified "
            "high-engagement sessions (e.g., workout playlists, study sessions) to reduce session abandonment — measure session completion rate delta. "
            "PM Hypothesis: Reducing ads during high-engagement moments will improve Free-to-Premium conversion rate by 8% MoM, as users experience "
            "premium-like flow states that create a desire for uninterrupted listening and lower the psychological barrier to upgrading. "
            "Secondary Action: Pilot a 'Premium Day Pass' bundle at ₹29 / $0.99 to capture impulsive upgrade intent — measure 7-day retention "
            "of day-pass buyers as a leading indicator for monthly subscription intent and LTV trajectory."
        )
    elif any(w in combined_text for w in ["ui", "layout", "design", "widget", "navigation", "interface", "home screen"]):
        theme_name = "Interface Layout and Navigation Disruption"
        action_idea = (
            "🎨 Feature: Launch a 'Spotify Home Lab' opt-in program where power users (>3h/day listening) beta-test modular home screen layouts, "
            "including re-orderable sections: Recently Played, Discover, Your Artists, and Mood Mixes. "
            "A/B Experiment: Test a 'Persistent Mini-Player' widget that stays anchored at the top during browsing — measure tap-through rate on "
            "contextual discovery tiles vs. the current implementation over 14 days across iOS and Android cohorts separately. "
            "PM Hypothesis: Users who customize their home layout will show a 40% increase in feature discovery engagement and 20% longer session "
            "durations due to reduced cognitive friction in navigation, with the highest impact seen in users with 1-6 months of tenure (onboarding cliff zone). "
            "Secondary Action: Conduct a 5-second usability test (via in-app micro-survey) with new users in their first 7 days to identify the #1 "
            "navigation confusion point — layer heatmap data on top of this to guide the Q3 redesign sprint with quantitative backing."
        )
    elif any(w in combined_text for w in ["crash", "slow", "bug", "lag", "stop", "freeze", "not working", "broken"]):
        theme_name = "App Performance and Stability Glitches"
        action_idea = (
            "🛠️ Feature: Implement 'Smart Preload Buffer' — an ML model that predicts the next 3 likely songs based on user queue behavior and "
            "caches them locally, preventing playback interruptions on unstable network connections. "
            "A/B Experiment: Roll out a 'Stability Sentinel' background process for 15% of Android users that monitors memory pressure and "
            "pre-emptively clears stale cache before the app reaches OOM thresholds — measure crash-free session rate delta over 30 days by device tier. "
            "PM Hypothesis: The preload buffer will reduce mid-session drop-offs by 35% for users in low-connectivity areas (3G or below), directly "
            "improving daily active listening minutes and 30-day retention in markets where network reliability is the #1 churn driver (India, SEA, LatAm). "
            "Secondary Action: Create a 'Performance Score' internal dashboard tracking P95 app launch time, track-load latency, and crash rate by "
            "device tier — use this to gate feature releases on sub-performing device segments and build a proactive SLO alerting system."
        )
    elif any(w in combined_text for w in ["discover", "recommend", "algorithm", "suggest", "new music", "find", "explore"]):
        theme_name = "Music Discovery Algorithm Opacity"
        action_idea = (
            "🔍 Feature: Introduce 'Why This Song?' — a contextual explanation panel (similar to Netflix's match score) surfacing 2-3 reasons "
            "why a track was recommended (e.g., 'Because you played X artist 4 times this week' or 'Trending among similar listeners in your city'). "
            "A/B Experiment: Test an 'Explainability Badge' on 30% of Discover Weekly tracks — measure if transparent algorithmic reasoning increases "
            "listen-through rate vs. control over 4 weeks, with secondary metrics on saves-to-library and playlist additions. "
            "PM Hypothesis: Algorithmic transparency will increase Discover Weekly full-listen rate by 18% and reduce the 'skip-on-first-listen' rate "
            "by 22%, as users feel informed rather than randomly served content, building long-term trust in Spotify's curation capabilities. "
            "Secondary Action: Build a 'Discovery Report' monthly card in each user's profile showing listening evolution (new genres explored, "
            "artists discovered, furthest genre leap from baseline) — design it as a shareable card to create organic viral growth loops."
        )
    elif any(w in combined_text for w in ["premium", "subscription", "price", "cost", "pay", "billing", "worth", "expensive", "cancel"]):
        theme_name = "Premium Value Perception Gap"
        action_idea = (
            "💎 Feature: Launch 'Premium Perks Hub' — a dedicated in-app page that dynamically showcases the value received this month: "
            "hours of ad-free listening saved, offline tracks downloaded, songs skipped, exclusive content unlocked, and estimated mobile data saved. "
            "A/B Experiment: Send a personalized 'Your Spotify Month in Numbers' push notification at day 25 of each billing cycle to 25% of at-risk "
            "churners (users with declining session frequency) — measure 30-day retention uplift and cancellation intent click-through vs. control. "
            "PM Hypothesis: Making the invisible value of Premium visible will reduce voluntary cancellations by 12% among users in their 3rd-6th month "
            "(the highest churn risk window) and improve NPS scores in the subscription tier by 7 points within two billing cycles. "
            "Secondary Action: Introduce a 'Pause Subscription' option (2–4 week pause with music access preserved) as a churn-prevention alternative "
            "to cancellation — A/B test its impact on 12-month LTV vs. users not offered the pause option, tracking reactivation rate and time-to-resubscribe."
        )
    elif any(w in combined_text for w in ["playlist", "mix", "daily mix", "radio", "station", "curated", "discover weekly"]):
        theme_name = "Playlist and Daily Mix Staleness"
        action_idea = (
            "🎵 Feature: Introduce 'Playlist Freshness Scoring' — an internal quality metric flagging Daily Mixes or Discover Weekly playlists "
            "that share >60% of tracks with the previous week's version, triggering forced algorithmic diversification before delivery to the user. "
            "A/B Experiment: Test 'Dynamic Daily Mix Refresh' for 20% of users — instead of a static weekly playlist, the Daily Mix updates every "
            "48 hours with a 30% new-track rotation, keeping the familiar core while continuously injecting novelty — measure open rates and session starts. "
            "PM Hypothesis: A 48-hour rotation cadence will increase Daily Mix open rates by 28% and re-engagement from dormant users (>7 days since "
            "last session) by 15%, as returning users encounter fresh content rather than the same stale playlist that drove disengagement. "
            "Secondary Action: Add a 'Not This Again' single-track feedback button directly in the playlist UI — aggregate these signals to train a "
            "per-user fatigue model that deprioritizes recently-heard tracks in generated playlists for a configurable 7-21 day cooldown window."
        )
    elif any(w in combined_text for w in ["offline", "download", "storage", "data", "internet", "network", "connection", "wifi"]):
        theme_name = "Offline Mode and Data Usage Friction"
        action_idea = (
            "📲 Feature: Build 'Smart Offline Sync' — an ML model predicting which playlists a user is most likely to listen to in the next 48 hours "
            "based on time-of-day patterns, location context, and calendar signals (e.g., commute times, gym check-ins), auto-downloading on Wi-Fi overnight. "
            "A/B Experiment: Test 'Adaptive Bitrate Offline Mode' — allow users to choose download quality per playlist (Standard 96kbps / High 160kbps / "
            "Max 320kbps) with an estimated storage footprint preview, directly reducing storage friction for budget-device users in emerging markets. "
            "PM Hypothesis: Predictive offline sync will increase the percentage of users with ≥1 offline playlist from 34% to 52%, directly improving "
            "retention among users in bandwidth-constrained markets (India, SEA, LatAm) where mobile data costs are a primary driver of listening session abandonment. "
            "Secondary Action: Introduce a 'Data Saver Mode' toggle that intelligently streams at adaptive low-bitrate when cellular data usage exceeds a "
            "user-set monthly threshold — measure impact on monthly active listening minutes in emerging markets vs. control."
        )
    
    # Get up to 3 representative quotes — use longest distinct reviews as they carry more signal
    seen = set()
    selected_quotes = []
    for text in sorted(review_texts, key=len, reverse=True):
        cleaned = text.strip()
        if cleaned and len(cleaned) > 10 and cleaned not in seen:
            seen.add(cleaned)
            selected_quotes.append(cleaned)
        if len(selected_quotes) >= 3:
            break
    if not selected_quotes:
        selected_quotes = [review_texts[0].strip()]
        
    return {
        "theme_name": theme_name,
        "action_idea": action_idea,
        "representative_quotes": selected_quotes
    }

def synthesize_cluster(cluster_reviews: list) -> dict:
    """
    Synthesizes a cluster: names it, pulls quotes, and suggests action ideas.
    Dynamically routes to LLM or local fallback.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        result = synthesize_cluster_llm(cluster_reviews, api_key)
        if result:
            return result
            
    return synthesize_cluster_local_fallback(cluster_reviews)

if __name__ == "__main__":
    # Test fallback
    test_reviews = [
        {"content": "I keep hearing the same songs on my shuffle. The repeat loop is so boring."},
        {"content": "Why is the loop repeating the same songs? Spotify is boring now."}
    ]
    res = synthesize_cluster(test_reviews)
    print("Fallback Synthesis Result:", json.dumps(res, indent=2))
