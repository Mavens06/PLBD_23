// ======== PAGES ========
function showPage(id, btn) {
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.bnav-item').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(btn) btn.classList.add('active');
  if(id==='map') { setTimeout(drawMap,100); }
  if(id==='expert') { setTimeout(drawPhChart,100); }
}


// ======== RECO PAGE ========
function showRecoTab(id, btn) {
  document.querySelectorAll('.reco-subpage').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.reco-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('reco-' + id).classList.add('active');
  if (btn) btn.classList.add('active');
  if (id === 'practices') { renderSoilPractices(); }
  if (id === 'temporal') { setTimeout(drawTemporalCharts, 80); setTimeout(drawTemporalHeatmap, 80); }
  if (id === 'cultures')  { renderCultureGrid('all'); }
}

function renderSoilPractices() {
  const container = document.getElementById('zonePracticeList');
  if (!container) return;
  const practices = [];
  for (let i = 0; i < ZONE_COUNT; i++) {
    const ph = mapData.ph[i], hum = mapData.humidity[i], ec = mapData.ec[i];
    const zone = String.fromCharCode(65 + Math.floor(i/6)) + (i%6 + 1);
    let priority = 'good', badge = '✓ Optimal', actions = [], reason = 'Paramètres optimaux';
    if (ph < 5.8) { priority = 'urgent'; badge = '⚠️ Urgent'; actions.push('<span class="zpc-action lime">🪨 Chaux : 1t/ha</span>'); reason = 'pH acide ('+ph.toFixed(1)+')'; }
    else if (ph > 8.2) { priority = 'warn'; badge = '⚡ Action'; actions.push('<span class="zpc-action lime">🧪 Soufre : 400kg/ha</span>'); reason = 'pH alcalin ('+ph.toFixed(1)+')'; }
    if (hum < 35) {
      const p = priority === 'urgent' ? 'urgent' : 'warn';
      priority = p; badge = p === 'urgent' ? '⚠️ Urgent' : '⚡ Action';
      actions.push('<span class="zpc-action water">💧 Irrigation : 20mm</span>');
      reason += (reason==='Paramètres optimaux'?'':'+ ') + 'Sol sec ('+hum.toFixed(0)+'%)';
    }
    if (ec > 2.5) {
      priority = 'urgent'; badge = '⚠️ Urgent';
      actions.push('<span class="zpc-action water">🌊 Lessivage : 35mm</span>');
      reason += (reason==='Paramètres optimaux'?'':'+ ') + 'Salinité ('+ec.toFixed(1)+' mS/cm)';
    }
    if (priority !== 'good') practices.push({ zone, priority, badge, actions, reason });
  }
  practices.sort((a,b) => (a.priority==='urgent'?-1:1));
  let html = practices.slice(0, 4).map(p => `
    <div class="zone-practice-card ${p.priority}">
      <div class="zpc-header"><span class="zpc-zone">Zone ${p.zone}</span><span class="zpc-badge ${p.priority}">${p.badge}</span></div>
      <div class="zpc-actions">${p.actions.join('')}</div>
      <div class="zpc-shap">IA : ${p.reason}</div>
    </div>`).join('');
  container.innerHTML = html || '<div class="zone-practice-card good"><div class="zpc-header"><span class="zpc-zone">Toutes zones</span><span class="zpc-badge good">✓ Optimal</span></div><div class="zpc-actions"><span class="zpc-action">✅ OK</span></div><div class="zpc-shap">IA : État du sol parfait.</div></div>';
}


function renderCultureGrid(filter) {
  currentCultureFilter = filter;
  const grid = document.getElementById('cultureGrid');
  if (!grid) return;
  const filtered = filter === 'all' ? CULTURES : CULTURES.filter(c => c.cat === filter);
  const sorted = [...filtered].sort((a,b) => b.match - a.match);
  grid.innerHTML = sorted.map(c => {
    const cls = c.match >= 80 ? 'match-high' : c.match >= 65 ? 'match-med' : 'match-low';
    const fillColor = c.match >= 80 ? '#4CAF50' : c.match >= 65 ? '#FFC107' : '#E53935';
    return `<div class="culture-card ${cls}">
      <div class="culture-emoji">${c.emoji}</div>
      <div class="culture-name">${c.name}</div>
      <div class="culture-match-bar">
        <div class="culture-match-fill" style="width:${c.match}%;background:${fillColor}"></div>
      </div>
      <div class="culture-match-label">${c.match}% compatibilité</div>
      <button class="culture-detail-btn" onclick="showCultureDetail('${c.id}')">Voir détails ▾</button>
    </div>`;
  }).join('');
}

function filterCultures(filter, btn) {
  document.querySelectorAll('.culture-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderCultureGrid(filter);
  document.getElementById('cultureDetailPanel').classList.remove('visible');
}

function showCultureDetail(id) {
  const c = CULTURES.find(x => x.id === id);
  if (!c) return;
  document.getElementById('cdpEmoji').textContent = c.emoji;
  document.getElementById('cdpName').textContent = c.name;
  document.getElementById('cdpDesc').textContent = c.desc;
  document.getElementById('cdpParams').innerHTML = [
    ['📅 Saison', c.season],
    ['💧 Eau', c.water],
    ['🧪 pH idéal', c.phRange],
    ['🌿 NPK', c.npk],
  ].map(([l,v]) => `<div class="cdp-param"><div class="cdp-param-label">${l}</div><div class="cdp-param-val">${v}</div></div>`).join('');
  const panel = document.getElementById('cultureDetailPanel');
  panel.classList.add('visible');
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function selectSession(idx, el) {
  document.querySelectorAll('.session-chip').forEach(c => c.classList.remove('active'));
  if (el) el.classList.add('active');
  // Update deltas (mock - compare to previous)
  const insights = [
    'Session initiale. Sol acide en B2 (pH 4.8), déficit N en A1. Recommandations émises.',
    'Légère amélioration pH B2 (+0.2) après apport partiel de chaux. N toujours faible.',
    'pH B2 progresse (5.2). N en baisse continue — apport urée non appliqué. Action urgente.',
  ];
  const insightEl = document.getElementById('temporalInsight');
  if (insightEl) insightEl.textContent = insights[idx] || insights[0];
  setTimeout(drawTemporalCharts, 50);
  setTimeout(drawTemporalHeatmap, 50);
}

// init cultures on first open
document.addEventListener('DOMContentLoaded', () => {
  renderCultureGrid('all');
  renderSoilPractices();
});

window.addEventListener('resize',()=>{ drawMap(); drawPhChart(); });
