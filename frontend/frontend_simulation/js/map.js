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
  if (currentMapVar === 'humidity') {
    return `<div class="leg-item"><span class="leg-dot" style="background:#2f80ed"></span>${t('weak')}</div><div class="leg-item"><span class="leg-dot" style="background:#4a9c55"></span>${t('correct')}</div><div class="leg-item"><span class="leg-dot" style="background:#e6a817"></span>${t('high')}</div><div class="leg-item"><span class="leg-dot" style="background:#d9e3da"></span>${t('unmeasured')}</div>`;
  }
  if (currentMapVar === 'ph') {
    return `<div class="leg-item"><span class="leg-dot" style="background:#c0392b"></span>${t('outRange')}</div><div class="leg-item"><span class="leg-dot" style="background:#e6a817"></span>${t('borderline')}</div><div class="leg-item"><span class="leg-dot" style="background:#4a9c55"></span>${t('correct')}</div><div class="leg-item"><span class="leg-dot" style="background:#d9e3da"></span>${t('unmeasured')}</div>`;
  }
  if (currentMapVar === 'ec') {
    return `<div class="leg-item"><span class="leg-dot" style="background:#c0392b"></span>&gt; 2.5 mS/cm</div><div class="leg-item"><span class="leg-dot" style="background:#e6a817"></span>1.5–2.5 mS/cm</div><div class="leg-item"><span class="leg-dot" style="background:#4a9c55"></span>&lt; 1.5 mS/cm</div><div class="leg-item"><span class="leg-dot" style="background:#d9e3da"></span>${t('unmeasured')}</div>`;
  }
  return `<div class="leg-item"><span class="leg-dot" style="background:#e6a817"></span>${t('borderline')}</div><div class="leg-item"><span class="leg-dot" style="background:#4a9c55"></span>${t('correct')}</div><div class="leg-item"><span class="leg-dot" style="background:#d9e3da"></span>${t('unmeasured')}</div>`;
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
  if (barEl) barEl.style.background = 'linear-gradient(90deg,#2f80ed,#c0392b,#e6a817,#4a9c55)';
  if (scaleEl) scaleEl.innerHTML = `<span>${t('scaleLow')}</span><span>${t('scaleGood')}</span>`;

  canvas.onclick = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const nearest = ZONES
      .map((z) => ({ z, d: Math.hypot(x - ZONE_POS[z].x*W, y - ZONE_POS[z].y*H) }))
      .sort((a, b) => a.d - b.d)[0].z;
    selectZone(nearest);
    showPage('reco', document.querySelector('[onclick*=reco]'));
  };
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
