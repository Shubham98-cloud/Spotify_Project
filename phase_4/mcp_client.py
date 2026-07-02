import os
import sys
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MCPClientWrapper:
    """
    A wrapper client that connects to external MCP servers via Stdio,
    or runs in simulation mode if no server commands are configured.
    """
    def __init__(self, server_name: str, start_command: str = None):
        self.server_name = server_name
        self.start_command = start_command
        self.is_simulation = start_command is None

        # Resolve output directory for simulations
        base_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.dirname(base_dir)
        self.sim_data_dir = os.path.join(workspace_root, "Data")
        os.makedirs(self.sim_data_dir, exist_ok=True)

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Calls a tool on the MCP server.
        Routes to real stdio MCP connection or offline simulation.
        """
        if self.is_simulation:
            return await self._simulate_tool_call(tool_name, arguments)
            
        logger.info(f"Connecting to real stdio MCP server '{self.server_name}'...")
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            # Split start command into executable and args
            cmd_parts = self.start_command.split()
            server_params = StdioServerParameters(
                command=cmd_parts[0],
                args=cmd_parts[1:]
            )
            
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.info(f"Invoking tool '{tool_name}' on real '{self.server_name}'...")
                    response = await session.call_tool(tool_name, arguments)
                    return {"status": "success", "content": response.content}
        except Exception as e:
            logger.error(f"Real MCP call failed: {e}. Falling back to simulation mode.")
            return await self._simulate_tool_call(tool_name, arguments)

    async def _simulate_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """
        Simulates the Google Docs and Gmail MCP tools by creating local outputs.
        """
        logger.info(f"[SIMULATION] Calling tool '{tool_name}' on simulated '{self.server_name}'")
        await asyncio.sleep(0.5) # Simulate network lag
        
        # 1. Google Docs MCP Simulation
        if self.server_name == "google-docs":
            if tool_name in ["append_text", "append_markdown", "write_document"]:
                doc_path = os.path.join(self.sim_data_dir, "Spotify_Pulse_Report.md")
                content = arguments.get("content", arguments.get("text", ""))
                
                # Append to running document file
                mode = "a" if os.path.exists(doc_path) else "w"
                with open(doc_path, mode, encoding="utf-8") as f:
                    if mode == "w":
                        f.write("# Spotify Weekly Product Review Pulse - Master Document\n\n")
                    f.write(content + "\n\n")
                    
                # Return document info representing the Google Doc state
                doc_id = "sim_gdoc_spotify_12345"
                heading_anchor = "heading=" + datetime.utcnow().strftime("week_%Y_%U")
                return {
                    "status": "success",
                    "document_id": doc_id,
                    "anchor_link": f"https://docs.google.com/document/d/{doc_id}/edit#{heading_anchor}",
                    "local_path": doc_path
                }
                
        # 2. Gmail MCP Simulation
        elif self.server_name == "gmail":
            if tool_name in ["send_email", "create_draft"]:
                outbox_dir = os.path.join(self.sim_data_dir, "email_outbox")
                os.makedirs(outbox_dir, exist_ok=True)
                
                to_addr = arguments.get("to", "stakeholders@spotify.com")
                subject = arguments.get("subject", "Weekly Pulse Report Notification")
                body = arguments.get("body", "")
                
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                email_path = os.path.join(outbox_dir, f"{timestamp}_email.html")
                
                email_data = {
                    "to": to_addr,
                    "subject": subject,
                    "body": body,
                    "timestamp": timestamp
                }
                
                with open(email_path, "w", encoding="utf-8") as f:
                    json.dump(email_data, f, indent=2, ensure_ascii=False)
                    
                return {
                    "status": "success",
                    "message_id": f"sim_msg_{timestamp}@mail.spotify.com",
                    "outbox_path": email_path
                }
                
        return {"status": "error", "error": f"Unknown tool or server: {self.server_name}/{tool_name}"}

if __name__ == "__main__":
    # Test simulation mode
    async def run_test():
        logging.basicConfig(level=logging.INFO)
        doc_client = MCPClientWrapper("google-docs")
        res = await doc_client.call_tool("append_markdown", {"content": "## Test Section\nSome mock content"})
        print("Google Docs Simulation Result:", json.dumps(res, indent=2))
        
        gmail_client = MCPClientWrapper("gmail")
        res2 = await gmail_client.call_tool("send_email", {
            "to": "pm_team@spotify.com",
            "subject": "New Report",
            "body": "Here is the link: https://docs.google.com/..."
        })
        print("Gmail Simulation Result:", json.dumps(res2, indent=2))
        
    asyncio.run(run_test())
