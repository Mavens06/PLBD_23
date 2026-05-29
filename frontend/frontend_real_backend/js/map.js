let currentMapVar = 'humidity';

function setVar(v, el) {
  currentMapVar = v;
  document.querySelectorAll('.map-var-btn').forEach((b) => b.classList.remove('active'));
  if (el) el.classList.add('active');
  drawMap();
}

function labelForMode() {
  return { humidity:t('mapHumidity'), ph:t('mapPh'), temp:t('mapTemp'), ec:t('mapEc') }[currentMapVar] || t('map');
}

function valueLabel(z) {
  if (!z) return t('unmeasured');
  if (currentMapVar === 'humidity') return `${z.humidity}%`;
  if (currentMapVar === 'ph') return `pH ${z.ph}`;
  if (currentMapVar === 'temp') return `${z.temp}°C`;
  if (currentMapVar === 'ec') return `${z.ec ?? '—'} mS/cm`;
  return '';
}

function legendForMode() {
  // Légende sémantique CONSTANTE (mêmes couleurs = même sens partout).
  const c = MAP_STATUS_COLORS;
  return (
    `<div class="leg-item"><span class="leg-dot" style="background:${c.good}"></span>${t('correct')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.warn}"></span>${t('borderline')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.bad}"></span>${t('outRange')}</div>` +
    `<div class="leg-item"><span class="leg-dot" style="background:${c.none}"></span>${t('unmeasured')}</div>`
  );
}

function drawMap() {
  const canvas = document.getElementById('fieldMap');
  if (!canvas) return;

  const W = canvas.offsetWidth || 360;
  canvas.width = W;
  canvas.height = Math.round(W * 0.66);
  const H = canvas.height;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = 'rgba(255,255,255,.04)';
  ctx.fillRect(0, 0, W, H);

  ZONES.forEach((zone) => {
    const pos = ZONE_POS[zone];
    const x = pos.x * W;
    const y = pos.y * H;
    const bw = W * .25;
    const bh = H * .20;
    const data = APP_STATE.fieldData[zone];
    const color = colorForVariable(data, currentMapVar);
    const label = valueLabel(data);

    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,.22)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = color;
    roundRect(ctx, x-bw/2, y-bh/2, bw, bh, 14);
    ctx.fill();
    ctx.restore();

    ctx.strokeStyle = zone === APP_STATE.selectedZone ? '#fff' : 'rgba(255,255,255,.45)';
    ctx.lineWidth = zone === APP_STATE.selectedZone ? 3 : 1;
    roundRect(ctx, x-bw/2, y-bh/2, bw, bh, 14);
    ctx.stroke();

    ctx.fillStyle = '#fff';
    ctx.font = '800 14px DM Sans';
    ctx.textAlign = 'center';
    ctx.fillText(zone, x, y-4);
    ctx.font = '700 10px DM Sans';
    ctx.fillText(label, x, y+14);
    if (data) {
      ctx.font = '10px DM Sans';
      ctx.fillText('✓', x+bw/2-12, y-bh/2+14);
    }
  });

  const rp = APP_STATE.robot.activePoint;
  if (ZONE_POS[rp]) {
    const p = ZONE_POS[rp];
    ctx.font = '26px serif';
    ctx.textAlign = 'center';
    ctx.fillText('🤖', p.x*W, p.y*H-30);
  }

  const labelEl = document.getElementById('mapVarLabel');
  const legendEl = document.getElementById('mapLegend');
  const barEl = document.getElementById('mapScaleBar');
  const scaleEl = document.getElementById('mapScaleLabels');
  if (labelEl) labelEl.textContent = labelForMode();
  if (legendEl) legendEl.innerHTML = legendForMode();
  // Échelle séquentielle cohérente : bon (vert) → limite (ambre) → à corriger (rouge).
  if (barEl) barEl.style.background = `linear-gradient(90deg,${MAP_STATUS_COLORS.good},${MAP_STATUS_COLORS.warn},${MAP_STATUS_COLORS.bad})`;
  if (scaleEl) scaleEl.innerHTML = `<span>${t('correct')}</span><span>${t('outRange')}</span>`;

  const zoneAt = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    return ZONES
      .map((z) => ({ z, d: Math.hypot(x - ZONE_POS[z].x*W, y - ZONE_POS[z].y*H) }))
      .sort((a, b) => a.d - b.d)[0].z;
  };

  canvas.onclick = (e) => {
    selectZone(zoneAt(e));
    showPage('reco', document.querySelector('[onclick*=reco]'));
  };

  // Survol : info-bulle avec la valeur de la zone la plus proche.
  const tip = document.getElementById('mapTooltip');
  if (tip) {
    canvas.onmousemove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const z = zoneAt(e);
      const data = APP_STATE.fieldData[z];
      const status = { good:t('correct'), warn:t('borderline'), bad:t('outRange'), none:t('unmeasured') }[variableStatus(data, currentMapVar)];
      tip.innerHTML = `<strong>${z}</strong> · ${valueLabel(data)}<br><span style="opacity:.8">${status}</span>`;
      tip.style.left = (e.clientX - rect.left + 12) + 'px';
      tip.style.top = (e.clientY - rect.top + 12) + 'px';
      tip.classList.add('show');
    };
    canvas.onmouseleave = () => tip.classList.remove('show');
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.arcTo(x+w, y, x+w, y+h, r);
  ctx.arcTo(x+w, y+h, x, y+h, r);
  ctx.arcTo(x, y+h, x, y, r);
  ctx.arcTo(x, y, x+w, y, r);
  ctx.closePath();
}
