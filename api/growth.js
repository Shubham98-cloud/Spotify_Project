const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const resolvedDir = path.join(process.cwd(), 'Data');
  const growthFile = path.join(resolvedDir, 'growth_experiments.json');

  if (req.method === 'GET') {
    let experiments = [];
    if (fs.existsSync(growthFile)) {
      try {
        experiments = JSON.parse(fs.readFileSync(growthFile, 'utf8'));
      } catch (e) {}
    }
    return res.status(200).json(experiments);
  }

  if (req.method === 'POST') {
    try {
      let experiments = [];
      if (fs.existsSync(growthFile)) {
        try {
          experiments = JSON.parse(fs.readFileSync(growthFile, 'utf8'));
        } catch (e) {}
      }
      
      const newCard = req.body;
      newCard.id = `card_${Math.floor(Date.now() / 1000)}`;
      newCard.created_at = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
      
      experiments.push(newCard);
      
      try {
        fs.writeFileSync(growthFile, JSON.stringify(experiments, null, 2), 'utf8');
      } catch (e) {}
      
      return res.status(200).json({ status: 'success', card: newCard });
    } catch (err) {
      return res.status(400).json({ status: 'error', message: err.message });
    }
  }
  
  res.status(405).json({ error: 'Method not allowed' });
};
