// ======== PH CHART ========
function drawPhChart() {
  const canvas=document.getElementById('phHistChart');
  if(!canvas) return;
  canvas.width=canvas.offsetWidth; canvas.height=80;
  const ctx=canvas.getContext('2d'), W=canvas.width, H=80;
  const days=['L','M','M','J','V','S','D'], ph=PH_HISTORY_7DAYS;
  const xS=(W-40)/(days.length-1);
  ctx.strokeStyle='#e8f5e9'; ctx.lineWidth=1;
  for(let i=0;i<=3;i++){ const y=10+(H-20)*i/3; ctx.beginPath();ctx.moveTo(20,y);ctx.lineTo(W-10,y);ctx.stroke(); }
  ctx.strokeStyle='#2d6a35'; ctx.lineWidth=2.5; ctx.beginPath();
  ph.forEach((v,i)=>{ const x=20+i*xS,y=10+(H-20)*(1-(v-5)/2); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.stroke();
  ph.forEach((v,i)=>{
    const x=20+i*xS,y=10+(H-20)*(1-(v-5)/2);
    ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);
    ctx.fillStyle='white';ctx.fill();ctx.strokeStyle='#2d6a35';ctx.lineWidth=2;ctx.stroke();
    ctx.fillStyle='#4a6b4e';ctx.font='10px DM Sans';ctx.textAlign='center';
    ctx.fillText(days[i],x,H-2); ctx.fillText(v,x,y-7);
  });
}

function healthColor(v) {
  if (v >= 80) return '#2E7D32';
  if (v >= 65) return '#4CAF50';
  if (v >= 50) return '#FFC107';
  if (v >= 35) return '#FF5722';
  return '#C62828';
}

function drawTemporalLine(canvasId, data, color, sessions) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  canvas.width = canvas.offsetWidth; canvas.height = 70;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = 70;
  const minV = Math.min(...data) * 0.95;
  const maxV = Math.max(...data) * 1.05;
  const xStep = (W - 40) / (data.length - 1 || 1);
  const yOf = v => 10 + (H - 20) * (1 - (v - minV) / ((maxV - minV) || 1));

  ctx.beginPath();
  data.forEach((v, i) => { const x = 20 + i * xStep, y = yOf(v); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.lineTo(20 + (data.length-1)*xStep, H); ctx.lineTo(20, H); ctx.closePath();
  ctx.fillStyle = color + '22'; ctx.fill();

  ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
  data.forEach((v, i) => { const x = 20 + i * xStep, y = yOf(v); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.stroke();

  data.forEach((v, i) => {
    const x = 20 + i * xStep, y = yOf(v);
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI*2);
    ctx.fillStyle = 'white'; ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#212121'; ctx.font = '9px DM Sans,sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(typeof v==='number'?(v%1===0?v:v.toFixed(1)):v, x, y - 8);
    ctx.fillStyle = '#9E9E9E'; ctx.font = '8px DM Sans,sans-serif';
    ctx.fillText(sessions[i].split(' ')[0], x, H - 2);
  });
}

function drawTemporalCharts() {
  const D = TEMPORAL_DATA;
  drawTemporalLine('temporalPhChart',  D.ph,  '#2E7D32', D.sessions);
  drawTemporalLine('temporalHumChart', D.hum, '#0277BD', D.sessions);
  drawTemporalLine('temporalEcChart',  D.ec,  '#6A1B9A', D.sessions);
}

function drawTemporalHeatmap() {
  const hm = document.getElementById('temporalHeatmap');
  if (!hm) return;
  hm.style.gridTemplateColumns = 'auto 1fr 1fr 1fr';
  let html = '';
  ['Zone','S1','S2','S3'].forEach(h => {
    html += `<div style="font-size:9px;font-weight:700;color:var(--grey);padding:2px 4px;text-align:center">${h}</div>`;
  });
  ZONES_HEALTH.slice(0,10).forEach((vals, zi) => {
    html += `<div style="font-size:9px;font-weight:700;color:var(--grey);padding:2px 4px;display:flex;align-items:center">${ZONE_LABELS_HM[zi]}</div>`;
    vals.forEach(v => {
      html += `<div class="thm-cell" style="background:${healthColor(v)}">${v}</div>`;
    });
  });
  hm.innerHTML = html;
}
