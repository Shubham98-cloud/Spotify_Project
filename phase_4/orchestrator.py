import os
import sys
import asyncio
import logging
from datetime import datetime

# Add workspace root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phase_3.pipeline import run_realtime_pipeline
from mcp_client import MCPClientWrapper

logger = logging.getLogger("phase_4_orchestrator")

def format_markdown_report(report: list, timestamp_str: str) -> str:
    """
    Formats the cluster results into a structured Markdown document
    suitable for appending to the Google Doc pulse log.
    """
    lines = []
    lines.append(f"## Week of {timestamp_str} (UTC)")
    lines.append("Here is the Weekly Product Review Pulse outlining customer friction themes, verbatim quotes, and actionable product ideas.\n")
    
    cluster_count = 0
    for item in report:
        if item["cluster_id"] == -1:
            continue
        cluster_count += 1
        lines.append(f"### Theme {cluster_count}: {item['theme_name'].upper()}")
        lines.append(f"*   **Sample Size:** {item['size']} reviews / complaints mentioned this week.")
        lines.append(f"*   **Suggested PM Action:** {item['action_idea']}")
        lines.append(f"*   **Representative Verbatim Quotes:**")
        for quote in item["representative_quotes"]:
            lines.append(f"    > \"{quote}\"")
        lines.append("")
        
    noise = next((item for item in report if item["cluster_id"] == -1), None)
    if noise:
        lines.append(f"### Unclustered Noise / General Feedback")
        lines.append(f"*   **Sample Size:** {noise['size']} reviews.")
        lines.append(f"*   **Sample Feedback:**")
        for quote in noise["representative_quotes"]:
            lines.append(f"    > \"{quote}\"")
        lines.append("")
        
    lines.append("---\n")
    return "\n".join(lines)

def format_email_body(report: list, doc_link: str, timestamp_str: str) -> str:
    """
    Formats a stakeholder email alert detailing top themes and
    providing a deep-link back to the master Google Doc.
    """
    lines = []
    lines.append(f"Hi Team,")
    lines.append(f"\nThe Spotify Weekly Product Review Pulse for the week of {timestamp_str} has been published.")
    lines.append(f"\n🔗 **Master Google Doc Link:** {doc_link}")
    lines.append(f"\n---")
    lines.append(f"\nSummary of Emergent Themes:")
    
    cluster_count = 0
    for item in report:
        if item["cluster_id"] == -1:
            continue
        cluster_count += 1
        lines.append(f"- **Theme #{cluster_count}:** {item['theme_name'].upper()} ({item['size']} mentions)")
        lines.append(f"  *PM Action Recommendation:* {item['action_idea']}")
        
    lines.append(f"\nPlease check the Google Doc link above for full verbatim quotes and historical logs.")
    lines.append(f"\nBest,")
    lines.append(f"\nGrowth Team Review Agent")
    return "\n".join(lines)

async def run_orchestration(timeframe: str = "7d", limit: int = 250, min_cluster_size: int = 2):
    """
    Runs Phase 3 real-time pipeline, formats outputs, and triggers MCP deliveries.
    """
    logger.info("Initializing Phase 4 Orchestration Run...")
    timestamp_str = datetime.utcnow().strftime("%B %d, %Y")
    
    # 1. Run Phase 3 Pipeline to scrape & cluster dynamically
    # Use centralized Data folder at the workspace root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(base_dir)
    output_dir = os.path.join(workspace_root, "Data")
    
    report = run_realtime_pipeline(
        timeframe=timeframe,
        limit_per_source=limit,
        min_cluster_size=min_cluster_size,
        output_dir=output_dir
    )
    
    if not report:
        logger.warning("No feedback parsed. Skipping MCP delivery.")
        return {"status": "skipped", "reason": "no reviews"}

    # 2. Format payloads
    md_content = format_markdown_report(report, timestamp_str)
    
    # 3. Deliver to Google Docs MCP
    gdoc_cmd = os.environ.get("GOOGLE_DOCS_MCP_COMMAND")
    gdoc_client = MCPClientWrapper("google-docs", gdoc_cmd)
    
    logger.info("Delivering Markdown report to Google Docs MCP...")
    gdoc_res = await gdoc_client.call_tool("append_markdown", {
        "content": md_content
    })
    
    doc_link = gdoc_res.get("anchor_link", "https://docs.google.com/document/d/sim_gdoc_spotify_12345/edit")
    
    # 4. Deliver to Gmail MCP
    email_body = format_email_body(report, doc_link, timestamp_str)
    gmail_cmd = os.environ.get("GMAIL_MCP_COMMAND")
    gmail_client = MCPClientWrapper("gmail", gmail_cmd)
    
    logger.info("Delivering Email Alert digest to Gmail MCP...")
    gmail_res = await gmail_client.call_tool("send_email", {
        "to": "stakeholders@spotify.com",
        "subject": f"[Spotify Pulse] Weekly Product Review Themes - {timestamp_str}",
        "body": email_body
    })
    
    logger.info("Orchestration Delivery complete!")
    return {
        "status": "success",
        "timestamp": timestamp_str,
        "google_doc_id": gdoc_res.get("document_id"),
        "google_doc_link": doc_link,
        "gmail_message_id": gmail_res.get("message_id"),
        "local_md_path": gdoc_res.get("local_path"),
        "local_email_path": gmail_res.get("outbox_path")
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Run orchestration simulation
    res = asyncio.run(run_orchestration(timeframe="30d", limit=250))
    print("\nOrchestration Result Details:\n", json.dumps(res, indent=2))
