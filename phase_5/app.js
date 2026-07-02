// Global State
let runsState = [];
let activeRunIndex = 0;
let cohortFilter = 'all';
let experimentsState = [];
let charts = {};

// Selectors
const selectRun = document.getElementById('select-run');
const runMetadata = document.getElementById('run-metadata');
const filterCohort = document.getElementById('filter-cohort');
const btnRefresh = document.getElementById('btn-refresh');

// Tab Switching Logic
const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');
const pageTitle = document.getElementById('page-title');
const pageSubtitle = document.getElementById('page-subtitle');

navItems.forEach(item => {
    item.addEventListener('click', () => {
        const tabName = item.getAttribute('data-tab');
        
        // Update Active Nav
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        
        // Update Active Pane
        tabPanes.forEach(pane => pane.classList.remove('active'));
        const activePane = document.getElementById(`pane-${tabName}`);
        if (activePane) activePane.classList.add('active');
        
        // Update Titles
        if (tabName === 'overview') {
            pageTitle.innerText = "Weekly Review Pulse";
            pageSubtitle.innerText = "AI-powered music discovery analysis";
        } else if (tabName === 'explorer') {
            pageTitle.innerText = "Theme Explorer";
            pageSubtitle.innerText = "Deep dive into customer friction points";
        } else if (tabName === 'trends') {
            pageTitle.innerText = "Temporal Trend Tracking";
            pageSubtitle.innerText = "Day-over-day friction delta analysis (past 30 days)";
            renderTemporalTrends(); // render trends line chart
        } else if (tabName === 'growth') {
            pageTitle.innerText = "Growth Loop Tracker";
            pageSubtitle.innerText = "Connect insights directly to PM validation cards";
            loadGrowthExperiments();
        }
    });
});

// Initial Load
window.addEventListener('DOMContentLoaded', async () => {
    await fetchRuns();
    await loadGrowthExperiments();
    checkSyncStatus(); // Monitor background ingestion runs
    
    // Bind Event Listeners
    if (selectRun) {
        selectRun.addEventListener('change', (e) => {
            activeRunIndex = parseInt(e.target.value);
            updateDashboard();
        });
    }
    
    filterCohort.addEventListener('change', (e) => {
        cohortFilter = e.target.value;
        updateDashboard();
    });
    
    btnRefresh.addEventListener('click', async () => {
        const originalText = btnRefresh.querySelector('span').innerText;
        btnRefresh.querySelector('span').innerText = "Loading...";
        await fetchRuns();
        btnRefresh.querySelector('span').innerText = originalText;
    });
    // Handle Growth Form Submit
    document.getElementById('growth-experiment-form').addEventListener('submit', createGrowthCard);

    // Auto-fill form fields when a theme is selected manually
    const expThemeSelect = document.getElementById('exp-theme');
    if (expThemeSelect) {
        expThemeSelect.addEventListener('change', (e) => {
            const selectedThemeName = e.target.value;
            if (!selectedThemeName) {
                document.getElementById('exp-title').value = "";
                document.getElementById('exp-hypothesis').value = "";
                document.getElementById('exp-metric').value = "";
                return;
            }
            
            const activeRun = runsState[activeRunIndex];
            if (activeRun && Array.isArray(activeRun.data)) {
                const themeData = activeRun.data.find(t => t.theme_name === selectedThemeName);
                if (themeData) {
                    const actionIdea = themeData.action_idea || "N/A";
                    document.getElementById('exp-title').value = `A/B Test: ${selectedThemeName}`;
                    document.getElementById('exp-hypothesis').value = `If we address the '${selectedThemeName}' complaint by implementing: ${actionIdea}, then we will increase active music discovery session metric Lifts.`;
                    document.getElementById('exp-metric').value = "+10% engagement lift"; // sensible default success metric
                }
            }
        });
    }
});

let isCurrentlySyncing = false;

async function checkSyncStatus() {
    const indicator = document.getElementById('sync-status-indicator');
    if (!indicator) return;
    
    try {
        const response = await fetch('/api/sync-status');
        const data = await response.json();
        
        if (data.is_fetching) {
            indicator.innerHTML = `
                <svg class="spinner" viewBox="0 0 50 50" style="width: 14px; height: 14px; animation: spin 1s linear infinite; stroke: #1db954; fill: none; stroke-width: 5; stroke-linecap: round; transform-origin: center;">
                    <circle cx="25" cy="25" r="20"></circle>
                </svg>
                <span style="color: #1db954;">Syncing...</span>
            `;
            if (!document.getElementById('spin-style')) {
                const style = document.createElement('style');
                style.id = 'spin-style';
                style.innerHTML = `@keyframes spin { 100% { transform: rotate(360deg); } }`;
                document.head.appendChild(style);
            }
            
            isCurrentlySyncing = true;
            setTimeout(checkSyncStatus, 3000);
        } else {
            if (isCurrentlySyncing) {
                indicator.innerHTML = `<span style="color: #1db954;">✅ Sync complete! Refreshing dashboard...</span>`;
                isCurrentlySyncing = false;
                await fetchRuns();
                setTimeout(() => {
                    indicator.innerHTML = '';
                }, 5000);
            } else {
                indicator.innerHTML = '';
            }
            setTimeout(checkSyncStatus, 10000);
        }
    } catch (e) {
        console.error("Failed to fetch sync status", e);
        setTimeout(checkSyncStatus, 15000);
    }
}

// Fetch Runs from API
async function fetchRuns() {
    try {
        const response = await fetch('/api/runs');
        const data = await response.json();
        
        // Filter out runs that are empty or have invalid types (we want runs that have clusters or reviews)
        runsState = data.filter(r => Array.isArray(r.data) && r.data.length > 0);
        
        // Merge similar/identical categories within each clustered run
        runsState.forEach(run => {
            if (run.type.includes('Clusters') && Array.isArray(run.data)) {
                const mergedMap = new Map();
                
                run.data.forEach(item => {
                    // Normalize name: lowercase, trim, replace multiple spaces with single space
                    const normName = item.theme_name.toLowerCase().trim().replace(/\s+/g, ' ');
                    
                    if (mergedMap.has(normName)) {
                        const existing = mergedMap.get(normName);
                        
                        // Merge reviews safely
                        const oldReviews = existing.reviews || [];
                        const newReviews = item.reviews || [];
                        existing.reviews = oldReviews.concat(newReviews);
                        
                        // Merge size
                        existing.size = existing.reviews.length || (existing.size || 0) + (item.size || 0);
                        
                        // Merge representative quotes (unique only)
                        const combinedQuotes = new Set([
                            ...(existing.representative_quotes || []),
                            ...(item.representative_quotes || [])
                        ]);
                        existing.representative_quotes = Array.from(combinedQuotes);
                        
                        // Keep the action idea of the larger cluster
                        if (newReviews.length > oldReviews.length) {
                            existing.action_idea = item.action_idea;
                        }
                    } else {
                        // Clone the item to avoid mutating original objects
                        mergedMap.set(normName, {
                            ...item,
                            representative_quotes: [...(item.representative_quotes || [])],
                            reviews: [...(item.reviews || [])]
                        });
                    }
                });
                
                run.data = Array.from(mergedMap.values());
            }
        });
        
        if (runsState.length === 0) {
            if (runMetadata) runMetadata.innerText = "No ingestion runs found in Data/.";
            return;
        }
        
        // Populate Ingestion Selector dropdown
        if (selectRun) {
            selectRun.innerHTML = "";
            runsState.forEach((run, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.innerText = `${run.pretty_time} (${run.type})`;
                selectRun.appendChild(option);
            });
            selectRun.value = 0;
        }
        
        activeRunIndex = 0;
        
        // Populate Experiment Theme dropdown
        populateExperimentThemeSelect();
        
        // Render Dashboard
        updateDashboard();
    } catch (e) {
        console.error("Failed to load runs", e);
        if (runMetadata) runMetadata.innerText = "Error fetching runs from API.";
    }
}

// Populate Theme Selector in Growth Loop Form
function populateExperimentThemeSelect() {
    const expThemeSelect = document.getElementById('exp-theme');
    if (!expThemeSelect) return;
    
    expThemeSelect.innerHTML = '<option value="">Select a theme...</option>';
    
    // Take the themes from the latest cluster run
    const latestClusteredRun = runsState.find(r => r.type.includes('Clusters'));
    if (latestClusteredRun && Array.isArray(latestClusteredRun.data)) {
        latestClusteredRun.data.forEach(theme => {
            if (theme.cluster_id !== -1) {
                const opt = document.createElement('option');
                opt.value = theme.theme_name;
                opt.innerText = theme.theme_name;
                expThemeSelect.appendChild(opt);
            }
        });
    }
}

// Cohort Filter Logic: Returns filtered reviews and size for a cluster item
function getFilteredClusterData(clusterItem, filter) {
    const reviews = clusterItem.reviews || [];
    if (filter === 'all') {
        return { reviews, size: reviews.length };
    }
    
    let filtered = [];
    if (filter === 'premium') {
        filtered = reviews.filter(r => {
            const segments = r.inferred_segments || [];
            return segments.some(s => s.toLowerCase().includes('premium')) || r.premium_status === true;
        });
    } else if (filter === 'free') {
        filtered = reviews.filter(r => {
            const segments = r.inferred_segments || [];
            return segments.some(s => s.toLowerCase().includes('free'));
        });
    } else if (filter === 'ios') {
        filtered = reviews.filter(r => r.source === 'app_store');
    } else if (filter === 'android') {
        filtered = reviews.filter(r => r.source === 'play_store');
    }
    
    return {
        reviews: filtered,
        size: filtered.length
    };
}

// Update Active Dashboard View
function updateDashboard() {
    if (runsState.length === 0 || !runsState[activeRunIndex]) return;
    
    const run = runsState[activeRunIndex];
    const isClustered = run.type.includes('Clusters');
    
    // Run Metadata
    if (runMetadata) {
        runMetadata.innerHTML = `
            <strong>Type:</strong> ${run.type}<br>
            <strong>Timestamp:</strong> ${run.timestamp}<br>
            <strong>Centralized File:</strong> Data/${run.filename}
        `;
    }
    
    // Parse clusters and statistics
    let clusters = [];
    if (isClustered) {
        clusters = run.data;
    } else {
        // Mock a single cluster out of raw/cleaned reviews if it's not a clustered run
        clusters = [{
            cluster_id: 1,
            theme_name: "General Feed Feedback",
            action_idea: "N/A - Review raw ingested data.",
            representative_quotes: run.data.slice(0, 3).map(r => r.content),
            reviews: run.data,
            size: run.data.length
        }];
    }
    
    // Apply Cohort Filters to calculate sizes
    let totalReviews = 0;
    let clusterCount = 0;
    let frictionReviewsCount = 0;
    
    const activeThemes = [];
    
    clusters.forEach(item => {
        const filteredData = getFilteredClusterData(item, cohortFilter);
        totalReviews += filteredData.size;
        
        if (item.cluster_id !== -1) {
            clusterCount++;
            activeThemes.push({
                ...item,
                filteredReviews: filteredData.reviews,
                filteredSize: filteredData.size
            });
            
            // Count repeating shuffle loop or recommendation issues as friction
            const lowerTheme = item.theme_name.toLowerCase();
            if (lowerTheme.includes('loop') || lowerTheme.includes('shuffle') || lowerTheme.includes('repeat') || lowerTheme.includes('recommend')) {
                frictionReviewsCount += filteredData.size;
            }
        } else {
            // Noise / General unclustered feedback
            activeThemes.push({
                ...item,
                theme_name: "Unclustered General Feedback",
                filteredReviews: filteredData.reviews,
                filteredSize: filteredData.size
            });
        }
    });
    
    // Update Metrics Cards
    document.getElementById('val-reviews').innerText = totalReviews;
    document.getElementById('val-themes').innerText = isClustered ? clusterCount : "N/A";
    
    const frictionPercentage = totalReviews > 0 ? Math.round((frictionReviewsCount / totalReviews) * 100) : 0;
    document.getElementById('val-friction').innerText = `${frictionPercentage}%`;
    
    // 1. Render Table
    renderOverviewTable(activeThemes);
    
    // 2. Render Explorer Cards
    renderExplorerCards(activeThemes);
    
    // 3. Render Dashboard Charts
    renderOverviewCharts(activeThemes);

    // 4. Render Top Affected User Segments
    renderAffectedSegments(activeThemes);
}

// Helper to classify theme sentiment and return happy/sad/neutral emoji
function getThemeSentimentEmoji(theme) {
    const reviews = theme.reviews || [];
    if (reviews.length === 0) {
        return "😐";
    }
    
    let sum = 0;
    reviews.forEach(r => {
        sum += r.rating || 0;
    });
    const avg = sum / reviews.length;
    
    if (avg >= 3.7) {
        return "😊";
    } else if (avg <= 2.5) {
        return "😞";
    } else {
        const lower = theme.theme_name.toLowerCase();
        if (lower.includes("fatigue") || lower.includes("frustration") || lower.includes("disruption") || lower.includes("glitch") || lower.includes("gap") || lower.includes("stale") || lower.includes("friction") || lower.includes("opacity")) {
            return "😞";
        }
        return "😐";
    }
}

// Render Top Affected User Segments & Needs
function renderAffectedSegments(themes) {
    const container = document.getElementById('overview-segments-container');
    if (!container) return;
    container.innerHTML = "";
    
    // Count occurrences of inferred segments across all reviews in all themes
    const segmentCounts = {};
    let totalReviewsCount = 0;
    
    themes.forEach(theme => {
        const reviews = theme.reviews || [];
        reviews.forEach(r => {
            totalReviewsCount++;
            const segments = r.inferred_segments || [];
            segments.forEach(seg => {
                segmentCounts[seg] = (segmentCounts[seg] || 0) + 1;
            });
        });
    });
    
    // Exclude General Feedback to focus on specific problem areas and user types
    delete segmentCounts["General Feedback"];
    
    // Convert to array and sort by count descending
    const sortedSegments = Object.keys(segmentCounts).map(seg => {
        return {
            name: seg,
            count: segmentCounts[seg],
            percentage: totalReviewsCount > 0 ? Math.round((segmentCounts[seg] / totalReviewsCount) * 100) : 0
        };
    }).sort((a, b) => b.count - a.count);
    
    // Map of segment names to their user needs/wants
    const needsMap = {
        "Premium User": "Wants personalized recommendations, true variety in shuffle, and high-quality offline playback without repetitiveness or profile stagnation.",
        "Free User": "Needs reasonable ad frequencies, functional basic player controls (skips), and discovery mixes that do not feel overly restricted.",
        "Discovery Issue": "Requires better recommendation algorithms, less familiarity bias/echo chambers, and controls to reset or adjust their music taste profiles.",
        "UI/UX Issue": "Wants clean navigation layouts, simple playlist/library organization, and functional, responsive player/queue controls.",
        "Performance/Stability Issue": "Needs app stability, fast launch times, reliable offline sync, and battery/storage optimizations."
    };
    
    // Take the top 3 affected segments
    const topSegments = sortedSegments.slice(0, 3);
    
    if (topSegments.length === 0) {
        container.innerHTML = `<div class="text-secondary" style="grid-column: 1 / -1;">No segment data available for this run.</div>`;
        return;
    }
    
    topSegments.forEach(seg => {
        const card = document.createElement('div');
        card.className = "glass";
        card.style.padding = "20px";
        card.style.borderRadius = "12px";
        card.style.borderLeft = "4px solid " + getSegmentColor(seg.name);
        
        const needDescription = needsMap[seg.name] || "Needs overall improvements and prompt responses to user feature requests.";
        
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <strong style="font-size:1.05rem; color:var(--text-primary);">${seg.name}</strong>
                <span class="badge theme-size" style="background:${getSegmentBg(seg.name)}; color:${getSegmentColor(seg.name)}; font-weight:600; padding:4px 8px; font-size:0.8rem;">
                    ${seg.percentage}% of reviews
                </span>
            </div>
            <div style="font-size:0.9rem; line-height:1.6; color:var(--text-primary);">
                <strong style="color:var(--text-secondary); display:block; font-size:0.75rem; text-transform:uppercase; margin-bottom:4px; letter-spacing:0.05em;">Core Need / Want</strong>
                ${needDescription}
            </div>
            <div style="font-size:0.8rem; color:var(--text-secondary); margin-top:12px;">
                Mentions: <strong>${seg.count}</strong> reviews in this dataset
            </div>
        `;
        container.appendChild(card);
    });
}

// Helpers for segment styling
function getSegmentColor(name) {
    if (name.includes("Premium")) return "#1db954";
    if (name.includes("Free")) return "#f1c40f";
    if (name.includes("Discovery")) return "#3498db";
    if (name.includes("UI")) return "#9b59b6";
    if (name.includes("Performance")) return "#e74c3c";
    return "#a8a8a8";
}

function getSegmentBg(name) {
    if (name.includes("Premium")) return "rgba(29, 185, 84, 0.15)";
    if (name.includes("Free")) return "rgba(241, 196, 15, 0.15)";
    if (name.includes("Discovery")) return "rgba(52, 152, 219, 0.15)";
    if (name.includes("UI")) return "rgba(155, 89, 182, 0.15)";
    if (name.includes("Performance")) return "rgba(231, 76, 60, 0.15)";
    return "rgba(168, 168, 168, 0.15)";
}

// Render Overview Table Elements
function renderOverviewTable(themes) {
    const tbody = document.getElementById('table-overview-themes');
    tbody.innerHTML = "";
    
    const sorted = themes.filter(t => t.cluster_id !== -1).sort((a,b) => b.filteredSize - a.filteredSize);
    
    if (sorted.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary">No themes match the selected filter.</td></tr>`;
        return;
    }
    
    sorted.forEach(t => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${getThemeSentimentEmoji(t)} ${t.theme_name}</strong></td>
            <td><span class="badge theme-size">${t.filteredSize} reviews</span></td>
            <td class="text-secondary">${t.action_idea}</td>
            <td><button class="view-details-link" onclick="openThemeDetails('${escapeHtml(JSON.stringify(t))}')">Deep Dive</button></td>
        `;
        tbody.appendChild(tr);
    });
}

// Render Theme Explorer Grid Cards
function renderExplorerCards(themes) {
    const grid = document.getElementById('explorer-theme-cards');
    grid.innerHTML = "";
    
    themes.forEach(t => {
        let pos = 0;
        let neg = 0;
        let neut = 0;
        const reviews = t.reviews || [];
        reviews.forEach(r => {
            if (r.rating >= 4) pos++;
            else if (r.rating <= 2) neg++;
            else neut++;
        });

        const card = document.createElement('div');
        card.className = "explorer-card glass";
        
        card.innerHTML = `
            <div class="explorer-card-header" style="margin: 0; width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 16px;">
                <h4 class="explorer-card-title" style="margin: 0; font-size: 1.1rem; font-weight: 600;">${getThemeSentimentEmoji(t)} ${t.theme_name}</h4>
                <span class="explorer-card-size">${t.filteredSize} reviews</span>
            </div>
            <div class="explorer-card-sentiment" style="margin-top: 12px; font-size: 0.85rem; color: var(--text-secondary); display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                <span style="display: flex; align-items: center; gap: 4px;">🟢 <strong style="color: #1db954;">Positive:</strong> ${pos}</span>
                <span style="display: flex; align-items: center; gap: 4px;">⚪ <strong style="color: #a8a8a8;">Neutral:</strong> ${neut}</span>
                <span style="display: flex; align-items: center; gap: 4px;">🔴 <strong style="color: #e74c3c;">Negative:</strong> ${neg}</span>
            </div>
        `;
        
        // Open detail on click
        card.addEventListener('click', () => {
            openThemeDetails(JSON.stringify(t));
        });
        
        grid.appendChild(card);
    });
}

// Render Dashboard Ingestion & Theme Charts
function renderOverviewCharts(themes) {
    // Destroy previous chart instances
    if (charts.themeDist) charts.themeDist.destroy();
    if (charts.cohortDist) charts.cohortDist.destroy();
    
    const activeThemesOnly = themes.filter(t => t.cluster_id !== -1);
    
    // Chart 1: Theme Distribution Bar Chart
    const ctxTheme = document.getElementById('chart-theme-distribution').getContext('2d');
    charts.themeDist = new Chart(ctxTheme, {
        type: 'bar',
        data: {
            labels: activeThemesOnly.map(t => t.theme_name.length > 20 ? t.theme_name.substring(0, 18) + '...' : t.theme_name),
            datasets: [{
                label: 'Cluster Complaint Size',
                data: activeThemesOnly.map(t => t.filteredSize),
                backgroundColor: [
                    'rgba(29, 185, 84, 0.65)',
                    'rgba(142, 68, 173, 0.65)',
                    'rgba(241, 196, 15, 0.65)',
                    'rgba(52, 152, 219, 0.65)',
                    'rgba(231, 76, 60, 0.65)'
                ],
                borderColor: [
                    '#1db954',
                    '#8e44ad',
                    '#f1c40f',
                    '#3498db',
                    '#e74c3c'
                ],
                borderWidth: 1.5,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#a7a7a7' } },
                y: { grid: { color: '#2a2a2a' }, ticks: { color: '#a7a7a7', stepSize: 1 } }
            }
        }
    });
    
    // Chart 2: Source breakdown
    const sourceStats = { app_store: 0, play_store: 0, reddit: 0 };
    themes.forEach(t => {
        t.filteredReviews.forEach(r => {
            if (sourceStats[r.source] !== undefined) {
                sourceStats[r.source]++;
            }
        });
    });
    
    const ctxCohort = document.getElementById('chart-cohorts').getContext('2d');
    charts.cohortDist = new Chart(ctxCohort, {
        type: 'doughnut',
        data: {
            labels: ['App Store (iOS)', 'Google Play (Android)', 'Reddit Threads'],
            datasets: [{
                data: [sourceStats.app_store, sourceStats.play_store, sourceStats.reddit],
                backgroundColor: [
                    'rgba(52, 152, 219, 0.7)',
                    'rgba(29, 185, 84, 0.7)',
                    'rgba(231, 76, 60, 0.7)'
                ],
                borderColor: '#181818',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#a7a7a7', padding: 16 }
                }
            },
            cutout: '65%'
        }
    });
}

// Render Temporal Trend Tracking (Phase 5 requirement)
function renderTemporalTrends() {
    if (charts.trends) charts.trends.destroy();
    
    // Find all runs that are clustered
    const clusteredRuns = runsState.filter(r => r.type.includes('Clusters')).reverse(); // sort chronologically
    if (clusteredRuns.length === 0) return;
    
    // Group runs by date (YYYYMMDD) within the past 30 days
    const dateMap = new Map();
    clusteredRuns.forEach(run => {
        const dateKey = run.timestamp.split('_')[0]; // "20260626"
        if (!dateKey) return;
        
        // Parse dateKey to check if it's within the past 30 days
        const year = parseInt(dateKey.substring(0, 4), 10);
        const month = parseInt(dateKey.substring(4, 6), 10) - 1;
        const day = parseInt(dateKey.substring(6, 8), 10);
        const runDate = new Date(year, month, day);
        
        const today = new Date();
        today.setHours(23, 59, 59, 999); // end of today
        const startOf30DaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
        startOf30DaysAgo.setHours(0, 0, 0, 0); // start of 30 days ago
        
        if (runDate < startOf30DaysAgo) {
            return; // Skip runs older than 30 days
        }
        
        if (!dateMap.has(dateKey)) {
            // Parse YYYYMMDD to pretty date (e.g. "Jun 26, 2026")
            const year = dateKey.substring(0, 4);
            const month = dateKey.substring(4, 6);
            const day = dateKey.substring(6, 8);
            const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const monthName = monthNames[parseInt(month, 10) - 1] || month;
            const prettyDate = `${monthName} ${parseInt(day, 10)}, ${year}`;
            
            dateMap.set(dateKey, {
                dateKey: dateKey,
                prettyDate: prettyDate,
                themes: new Map(), // normName -> { theme_name, size, rawSize }
                totalSize: 0
            });
        }
        
        const dayGroup = dateMap.get(dateKey);
        run.data.forEach(theme => {
            const themeSize = theme.reviews ? theme.reviews.length : (theme.size || 0);
            dayGroup.totalSize += themeSize;
            
            // Only aggregate clustered themes (exclude noise/unclustered general feedback with cluster_id === -1)
            if (theme.cluster_id !== -1) {
                const normName = theme.theme_name.toLowerCase().trim().replace(/\s+/g, ' ');
                if (dayGroup.themes.has(normName)) {
                    const existing = dayGroup.themes.get(normName);
                    existing.size += themeSize;
                    if (themeSize > existing.rawSize) {
                        existing.theme_name = theme.theme_name;
                        existing.rawSize = themeSize;
                    }
                } else {
                    dayGroup.themes.set(normName, {
                        theme_name: theme.theme_name,
                        size: themeSize,
                        rawSize: themeSize
                    });
                }
            }
        });
    });
    
    // Sort chronological dates
    const dailyAggregates = Array.from(dateMap.values()).sort((a, b) => a.dateKey.localeCompare(b.dateKey));
    
    // Extract unique theme names
    const allThemeNames = new Set();
    dailyAggregates.forEach(day => {
        for (const [_, theme] of day.themes) {
            allThemeNames.add(theme.theme_name);
        }
    });
    
    const dates = dailyAggregates.map(d => d.prettyDate);
    const datasets = [];
    const colorPalette = [
        '#1db954',
        '#8e44ad',
        '#f1c40f',
        '#3498db',
        '#e74c3c',
        '#e67e22',
        '#1abc9c'
    ];
    
    let colorIdx = 0;
    allThemeNames.forEach(themeName => {
        const dataPoints = [];
        
        dailyAggregates.forEach(day => {
            let themeSize = 0;
            for (const [normName, theme] of day.themes) {
                if (theme.theme_name.toLowerCase().trim() === themeName.toLowerCase().trim()) {
                    themeSize = theme.size;
                    break;
                }
            }
            const pct = day.totalSize > 0 ? parseFloat(((themeSize / day.totalSize) * 100).toFixed(1)) : 0;
            dataPoints.push(pct);
        });
        
        datasets.push({
            label: themeName,
            data: dataPoints,
            borderColor: colorPalette[colorIdx % colorPalette.length],
            backgroundColor: colorPalette[colorIdx % colorPalette.length] + '22',
            borderWidth: 2.5,
            tension: 0.3,
            fill: false
        });
        colorIdx++;
    });
    
    const ctxTrends = document.getElementById('chart-temporal-trends').getContext('2d');
    charts.trends = new Chart(ctxTrends, {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#a7a7a7', boxWidth: 12 }
                }
            },
            scales: {
                x: { grid: { color: '#2a2a2a' }, ticks: { color: '#a7a7a7' } },
                y: { 
                    grid: { color: '#2a2a2a' }, 
                    ticks: { color: '#a7a7a7' },
                    title: { display: true, text: 'Theme Share of Total Complaints (%)', color: '#a7a7a7' }
                }
            }
        }
    });
    
    // Generate Trend Alerts (Day-Over-Day percentage jumps)
    generateTrendAlerts(dailyAggregates);
}

// Generate warnings if complaints on a theme jump significantly
function generateTrendAlerts(dailyAggregates) {
    const alertsContainer = document.getElementById('trend-alerts-container');
    alertsContainer.innerHTML = "";
    
    if (dailyAggregates.length < 2) {
        alertsContainer.innerHTML = `
            <div class="alert-card glass" style="grid-column: 1 / -1; border-color: var(--border-color); background: transparent;">
                <span class="alert-title text-muted">A minimum of 2 historical days are required to track temporal daily alerts. Run the ingestion pipeline again on different days to generate data.</span>
            </div>
        `;
        return;
    }
    
    // Compare the latest day (last in list) with the previous day
    const latestDay = dailyAggregates[dailyAggregates.length - 1];
    const prevDay = dailyAggregates[dailyAggregates.length - 2];
    
    const latestTotal = latestDay.totalSize;
    const prevTotal = prevDay.totalSize;
    
    let alertsTriggered = 0;
    
    for (const [normName, latestTheme] of latestDay.themes) {
        const latestSize = latestTheme.size;
        const latestPct = latestTotal > 0 ? (latestSize / latestTotal) * 100 : 0;
        
        // Find in prev day
        let prevTheme = null;
        for (const [prevNormName, t] of prevDay.themes) {
            if (prevNormName === normName) {
                prevTheme = t;
                break;
            }
        }
        
        const prevSize = prevTheme ? prevTheme.size : 0;
        const prevPct = prevTotal > 0 ? (prevSize / prevTotal) * 100 : 0;
        
        // Trigger alert if share of complaints increases by > 1.5x (50% increase) and is significant (> 5%)
        if (prevPct > 0 && latestPct >= prevPct * 1.5 && latestPct > 5) {
            alertsTriggered++;
            const alertCard = document.createElement('div');
            alertCard.className = "alert-card";
            alertCard.innerHTML = `
                <div class="alert-icon">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01"/></svg>
                </div>
                <div>
                    <h4 class="alert-title">Critical Spike Detected: ${latestTheme.theme_name.toUpperCase()}</h4>
                    <p class="alert-desc">Theme complaints jumped significantly day-over-day. Current complaint share: <strong>${latestPct.toFixed(1)}%</strong> (up from <strong>${prevPct.toFixed(1)}%</strong>). Recommending immediate review of algorithm adjustments or UI components.</p>
                </div>
            `;
            alertsContainer.appendChild(alertCard);
        }
    }
    
    if (alertsTriggered === 0) {
        alertsContainer.innerHTML = `
            <div class="alert-card glass" style="grid-column: 1 / -1; border-color: rgba(29, 185, 84, 0.3); background: rgba(29, 185, 84, 0.05); color: var(--spotify-green)">
                <div style="color: var(--spotify-green)">
                    <h4 class="alert-title" style="color: var(--spotify-green)">✓ Dynamic System Stable</h4>
                    <p class="alert-desc" style="color: var(--text-primary)">No daily Spikes or anomalous complaint surges detected across the tracking timeframe. Music discovery feedback remains within baseline variations.</p>
                </div>
            </div>
        `;
    }
}

// Open Theme Detail Sidebar Modal
function openThemeDetails(themeString) {
    const t = JSON.parse(themeString);
    const modal = document.getElementById('modal-theme');
    const body = document.getElementById('modal-theme-body');
    
    // Calculate cohort stats
    let freeCount = 0;
    let premiumCount = 0;
    let iosCount = 0;
    let androidCount = 0;
    let positiveCount = 0;
    let negativeCount = 0;
    let neutralCount = 0;
    
    t.reviews.forEach(r => {
        const segments = r.inferred_segments || [];
        if (segments.some(s => s.toLowerCase().includes('premium')) || r.premium_status === true) premiumCount++;
        if (segments.some(s => s.toLowerCase().includes('free'))) freeCount++;
        if (r.source === 'app_store') iosCount++;
        if (r.source === 'play_store') androidCount++;

        const rating = r.rating || 0;
        if (rating >= 4) positiveCount++;
        else if (rating <= 2) negativeCount++;
        else neutralCount++;
    });
    
    let quotesHtml = "";
    t.representative_quotes.forEach(quote => {
        quotesHtml += `<div class="quote-block">"${quote}"</div>`;
    });
    
    body.innerHTML = `
        <h2 class="modal-title">${getThemeSentimentEmoji(t)} ${t.theme_name}</h2>
        <div>
            <span class="badge theme-size" style="font-size: 0.9rem; padding: 6px 12px;">Total Mentions: ${t.reviews.length} complaints</span>
        </div>
        
        <div>
            <h4 class="modal-section-title">Friction Cohort Segmentations</h4>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:10px;">
                <div class="glass" style="padding:16px; text-align:center;">
                    <div style="font-size:0.8rem; color:var(--text-secondary)">Premium vs Free</div>
                    <div style="font-size:1.25rem; font-weight:700; margin-top:4px;">${premiumCount} / ${freeCount}</div>
                </div>
                <div class="glass" style="padding:16px; text-align:center;">
                    <div style="font-size:0.8rem; color:var(--text-secondary)">iOS vs Android</div>
                    <div style="font-size:1.25rem; font-weight:700; margin-top:4px;">${iosCount} / ${androidCount}</div>
                </div>
            </div>
        </div>

        <div>
            <h4 class="modal-section-title">Sentiment Classification Breakdown</h4>
            <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:16px; margin-top:10px;">
                <div class="glass" style="padding:16px; text-align:center; border-bottom: 3px solid #1db954;">
                    <div style="font-size:0.8rem; color:var(--text-secondary)">😊 Positive Feedback</div>
                    <div style="font-size:1.25rem; font-weight:700; margin-top:4px; color:#1db954;">${positiveCount}</div>
                </div>
                <div class="glass" style="padding:16px; text-align:center; border-bottom: 3px solid #a8a8a8;">
                    <div style="font-size:0.8rem; color:var(--text-secondary)">😐 Neutral Feedback</div>
                    <div style="font-size:1.25rem; font-weight:700; margin-top:4px; color:#a8a8a8;">${neutralCount}</div>
                </div>
                <div class="glass" style="padding:16px; text-align:center; border-bottom: 3px solid #e74c3c;">
                    <div style="font-size:0.8rem; color:var(--text-secondary)">😞 Negative Feedback</div>
                    <div style="font-size:1.25rem; font-weight:700; margin-top:4px; color:#e74c3c;">${negativeCount}</div>
                </div>
            </div>
        </div>

        <div>
            <h4 class="modal-section-title">Suggested PM Action Item</h4>
            <div class="glass" style="padding:20px; font-weight:500; line-height:1.5; border-left:4px solid var(--spotify-green);">
                ${t.action_idea}
            </div>
        </div>

        <div>
            <h4 class="modal-section-title">Representative Verbatim Quotes (100% verified)</h4>
            <div style="margin-top:12px;">
                ${quotesHtml}
            </div>
        </div>
        
        <div style="margin-top: 10px;">
            <button class="submit-btn" onclick="triggerGrowthLink('${escapeHtml(t.theme_name)}', '${escapeHtml(t.action_idea)}')">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
                <span>Link to Growth Experiment Loop</span>
            </button>
        </div>
    `;
    
    modal.classList.add('active');
    
    // Bind Close Elements
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', closeModal);
}

function closeModal() {
    document.getElementById('modal-theme').classList.remove('active');
}

// Pre-fill growth loop form from deep dive action item
function triggerGrowthLink(themeName, actionIdea) {
    closeModal();
    // Switch to Growth Loop tab
    document.getElementById('btn-growth').click();
    
    // Fill form
    document.getElementById('exp-theme').value = themeName;
    document.getElementById('exp-title').value = `A/B Test: ${themeName}`;
    document.getElementById('exp-hypothesis').value = `If we address the '${themeName}' complaint by implementing: ${actionIdea}, then we will increase active music discovery session metric Lifts.`;
}

// Fetch growth experiments from local server API
async function loadGrowthExperiments() {
    try {
        const response = await fetch('/api/growth');
        experimentsState = await response.json();
        
        const board = document.getElementById('growth-cards-board');
        board.innerHTML = "";
        
        if (experimentsState.length === 0) {
            board.innerHTML = `
                <div class="text-center text-secondary" style="padding: 40px;">
                    No active growth experiments found. Submit the form on the left to spawn A/B test experiment cards.
                </div>
            `;
            return;
        }
        
        // Render cards
        experimentsState.forEach(exp => {
            const card = document.createElement('div');
            card.className = "experiment-board-card";
            card.innerHTML = `
                <div class="experiment-card-header">
                    <h4 class="experiment-card-title">${exp.title}</h4>
                    <span class="experiment-card-meta">${exp.created_at}</span>
                </div>
                <p class="experiment-card-hypothesis"><strong>Hypothesis:</strong> ${exp.hypothesis}</p>
                <div class="experiment-card-footer">
                    <div class="experiment-card-badges">
                        <span class="badge blue">${exp.cohort}</span>
                        <span class="badge purple">Lift: ${exp.metric}</span>
                    </div>
                    <span class="badge green">Status: A/B Testing</span>
                </div>
            `;
            board.appendChild(card);
        });
    } catch (e) {
        console.error("Failed to load growth experiments", e);
    }
}

// Post growth experiment to local server API
async function createGrowthCard(e) {
    e.preventDefault();
    
    const themeName = document.getElementById('exp-theme').value;
    const title = document.getElementById('exp-title').value;
    const hypothesis = document.getElementById('exp-hypothesis').value;
    const cohort = document.getElementById('exp-cohort').value;
    const metric = document.getElementById('exp-metric').value;
    
    if (!themeName || !title || !hypothesis || !metric) return;
    
    const payload = {
        theme_name: themeName,
        title: title,
        hypothesis: hypothesis,
        cohort: cohort,
        metric: metric
    };
    
    try {
        const response = await fetch('/api/growth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const res = await response.json();
        if (res.status === 'success') {
            // Reset form
            document.getElementById('growth-experiment-form').reset();
            // Reload list
            await loadGrowthExperiments();
        }
    } catch (err) {
        console.error("Failed to post growth experiment", err);
    }
}

// Helper to escape HTML tags in strings
function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
