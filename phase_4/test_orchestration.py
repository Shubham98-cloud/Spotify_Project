import os
import json
import asyncio
import logging
from orchestrator import run_orchestration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_orchestration")

def verify_markdown_formatting(file_path: str):
    """
    Checks that the simulated Google Doc Markdown file contains correct sections and formats.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check headers and tags
    assert "Spotify Weekly Product Review Pulse - Master Document" in content, "Missing main title header"
    assert "## Week of" in content, "Missing weekly timestamp section"
    assert "### Theme" in content or "Unclustered" in content, "Missing theme sections"
    assert "Suggested PM Action:" in content, "Missing action items"
    assert "Representative Verbatim Quotes:" in content, "Missing quote sections"
    
    logger.info("✓ Simulated Google Doc Markdown formatting looks correct.")

def verify_email_formatting(file_path: str):
    """
    Checks that the simulated Gmail JSON outbox file contains correct fields and links.
    """
    assert os.path.exists(file_path), f"File not found: {file_path}"
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("to") == "stakeholders@spotify.com", "Recipient mismatch"
    assert "[Spotify Pulse] Weekly Product Review Themes -" in data.get("subject", ""), "Subject mismatch"
    
    body = data.get("body", "")
    assert "Master Google Doc Link:" in body, "Missing document deep link in email body"
    assert "Theme #" in body, "Missing theme list in email body"
    assert "PM Action Recommendation:" in body, "Missing recommendations in email body"
    
    logger.info("✓ Simulated Gmail Alert body looks correct.")

async def run_checks():
    logger.info("Starting Phase 4 automated verification checks...")
    
    # Run orchestrator in simulation mode (fetching only 5 items per source to be fast)
    res = await run_orchestration(timeframe="30d", limit=5)
    
    assert res.get("status") == "success", "Orchestration run failed"
    
    # 1. Verify Google Doc simulated output file
    gdoc_path = res.get("local_md_path")
    verify_markdown_formatting(gdoc_path)
    
    # 2. Verify Gmail simulated output file
    gmail_path = res.get("local_email_path")
    verify_email_formatting(gmail_path)
    
    logger.info("=" * 60)
    logger.info("  ALL PHASE 4 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_checks())
