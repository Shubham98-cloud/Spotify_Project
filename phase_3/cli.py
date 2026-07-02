import os
import sys
import argparse
import logging
from pipeline import run_realtime_pipeline

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description="Spotify Real-Time Review Discovery CLI")
    parser.add_argument(
        "--timeframe", 
        type=str, 
        default="7d", 
        help="Timeframe to query reviews. Options: '24h', '7d', '30d' (default: '7d')"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=250, 
        help="Maximum reviews to fetch per ingestion source (default: 250 → targets ~500+ total)"
    )
    parser.add_argument(
        "--min-cluster-size", 
        type=int, 
        default=2, 
        help="Minimum cluster size to form a theme (default: 2)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="Data", 
        help="Directory to save output analytics JSON (default: 'Data')"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable detailed log outputs"
    )

    args = parser.parse_args()

    # Configure logging level
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    print("\n" + "="*70)
    print("      INITIALIZING SPOTIFY REAL-TIME MUSIC DISCOVERY ANALYTICS")
    print("="*70)
    print(f"Timeframe Window  : {args.timeframe}")
    print(f"Limit per Source  : {args.limit} reviews")
    print(f"Min Cluster Size  : {args.min_cluster_size} reviews")
    print("Fetching live data. Please wait...\n")

    # Resolve output directory absolute path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(base_dir)
    if not os.path.isabs(args.output_dir):
        # Resolve relative to workspace root, mapping 'data' to 'Data'
        folder_name = "Data" if args.output_dir.lower() == "data" else args.output_dir
        target_output_dir = os.path.join(workspace_root, folder_name)
    else:
        target_output_dir = args.output_dir

    try:
        report = run_realtime_pipeline(
            timeframe=args.timeframe,
            limit_per_source=args.limit,
            min_cluster_size=args.min_cluster_size,
            output_dir=target_output_dir
        )
        
        if not report:
            print("\n[!] No clusters formed. Try increasing the timeframe window or review limit.")
            return

        # Render Beautiful PM Pulse Report
        print("\n" + "╔" + "═"*68 + "╗")
        print("║" + " "*23 + "WEEKLY PRODUCT REVIEW PULSE" + " "*22 + "║")
        print("╠" + "═"*68 + "╣")
        
        cluster_count = 0
        for item in report:
            if item["cluster_id"] == -1:
                continue
            cluster_count += 1
            print(f"║ 📂 THEME #{cluster_count}: {item['theme_name'].upper():<51} ║")
            print(f"║   • Size: {item['size']} user complaints / feedback mentions                      ║")
            
            # Wrap action idea nicely
            action = item["action_idea"]
            action_lines = []
            while len(action) > 60:
                split_idx = action[:60].rfind(" ")
                if split_idx == -1:
                    split_idx = 60
                action_lines.append(action[:split_idx].strip())
                action = action[split_idx:].strip()
            action_lines.append(action)
            
            print(f"║   • PM Action: {action_lines[0]:<50} ║")
            for line in action_lines[1:]:
                print(f"║                {line:<50} ║")
                
            print("║   • Verbatim Quotes:                                               ║")
            for quote in item["representative_quotes"]:
                # Wrap quote text
                q_text = f'"{quote}"'
                q_lines = []
                while len(q_text) > 58:
                    split_idx = q_text[:58].rfind(" ")
                    if split_idx == -1:
                        split_idx = 58
                    q_lines.append(q_text[:split_idx].strip())
                    q_text = q_text[split_idx:].strip()
                q_lines.append(q_text)
                
                print(f"║      - {q_lines[0]:<58} ║")
                for q_line in q_lines[1:]:
                    print(f"║        {q_line:<58} ║")
            print("╠" + "─"*68 + "╣")
            
        noise = next((item for item in report if item["cluster_id"] == -1), None)
        noise_size = noise["size"] if noise else 0
        print(f"║ 💬 Unclustered Noise/General Feedback: {noise_size:<28} reviews ║")
        print("╚" + "═"*68 + "╝\n")

    except Exception as e:
        print(f"\n[ERROR] Pipeline execution failed: {e}")

if __name__ == "__main__":
    main()
