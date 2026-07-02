const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');
  
  try {
    const resolvedDir = path.join(process.cwd(), 'Data');
    const runs = [];
    
    if (fs.existsSync(resolvedDir)) {
      const files = fs.readdirSync(resolvedDir);
      files.forEach(f => {
        if (f.endsWith('.json') && f !== 'growth_experiments.json' && (f.startsWith('cluster_results_') || f.startsWith('realtime_clusters_'))) {
          const filePath = path.join(resolvedDir, f);
          const content = fs.readFileSync(filePath, 'utf8');
          const runData = JSON.parse(content);
          
          let timestamp = "";
          let runType = "other";
          if (f.includes('realtime_clusters_')) {
            timestamp = f.replace('realtime_clusters_', '').replace('.json', '');
            runType = 'Real-Time Clusters';
          } else if (f.includes('cluster_results_')) {
            timestamp = f.replace('cluster_results_', '').replace('.json', '');
            runType = 'Static Clusters';
          } else {
            timestamp = f.replace('.json', '');
          }
          
          let prettyTime = timestamp;
          try {
            // timestamp format: YYYYMMDD_HHMMSS
            const year = timestamp.substring(0, 4);
            const month = timestamp.substring(4, 6);
            const day = timestamp.substring(6, 8);
            const hour = timestamp.substring(9, 11);
            const min = timestamp.substring(11, 13);
            const sec = timestamp.substring(13, 15);
            
            const dt = new Date(year, parseInt(month) - 1, day, hour, min, sec);
            prettyTime = dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ' ' + dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
          } catch (e) {}
          
          runs.push({
            filename: f,
            timestamp: timestamp,
            pretty_time: prettyTime,
            type: runType,
            data: runData
          });
        }
      });
    }
    
    // Sort descending by timestamp (newest first)
    runs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    res.status(200).json(runs);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
