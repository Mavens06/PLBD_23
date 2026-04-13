// ======== PH CHART ========
function drawPhChart() {
  const canvas=document.getElementById('phHistChart');
  if(!canvas) return;
  canvas.width=canvas.offsetWidth; canvas.height=80;
  const ctx=canvas.getContext('2d'), W=canvas.width, H=80;
  const days=['L','M','M','J','V','S','D'], ph=[6.1,6.3,6.2,6.5,6.4,6.3,6.4];
  const xS=(W-40)/(days.length-1);
  ctx.strokeStyle='#e8f5e9'; ctx.lineWidth=1;
  for(let i=0;i<=3;i++){ const y=10+(H-20)*i/3; ctx.beginPath();ctx.moveTo(20,y);ctx.lineTo(W-10,y);ctx.stroke(); }
  ctx.strokeStyle='#2d6a35'; ctx.lineWidth=2.5; ctx.beginPath();
  ph.forEach((v,i)=>{ const x=20+i*xS,y=10+(H-20)*(1-(v-5)/3.5); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.stroke();
  ph.forEach((v,i)=>{
    const x=20+i*xS,y=10+(H-20)*(1-(v-5)/3.5);
    ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);
    ctx.fillStyle='white';ctx.fill();ctx.strokeStyle='#2d6a35';ctx.lineWidth=2;ctx.stroke();
    ctx.fillStyle='#4a6b4e';ctx.font='10px DM Sans';ctx.textAlign='center';
    ctx.fillText(days[i],x,H-2); ctx.fillText(v,x,y-7);
  });
}



const TEMPORAL_DATA = {
  sessions: ['S1 – 08/03', 'S2 – 10/03', 'S3 – 12/03'],
  ph:  [4.8, 5.0, 5.2],
  hum: [41,  43,  42],
  n:   [21,  19,  18],
};

const ZONES_HEALTH = [
  [55, 72, 80], [40, 48, 62], [88, 90, 91], [30, 35, 50],
  [65, 70, 74], [78, 80, 83], [22, 28, 40], [55, 60, 65],
  [90, 91, 92], [44, 50, 55], [66, 68, 70], [38, 42, 48],
  [80, 82, 85], [58, 62, 68], [72, 74, 78],
];
const ZONE_LABELS_HM = ['A1','A2','A3','B1','B2','B3','C1','C2','C3','D1','D2','D3','D4','E1','E2'];

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
  const xStep = (W - 40) / (data.length - 1);
  const yOf = v => 10 + (H - 20) * (1 - (v - minV) / (maxV - minV));

  // Area fill
  ctx.beginPath();
  data.forEach((v, i) => { const x = 20 + i * xStep, y = yOf(v); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.lineTo(20 + (data.length-1)*xStep, H); ctx.lineTo(20, H); ctx.closePath();
  ctx.fillStyle = color + '22'; ctx.fill();

  // Line
  ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
  data.forEach((v, i) => { const x = 20 + i * xStep, y = yOf(v); i===0?ctx.moveTo(x,y):ctx.lineTo(x,y); });
  ctx.stroke();

  // Dots + labels
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
  drawTemporalLine('temporalNChart',   D.n,   '#6A1B9A', D.sessions);
}

function drawTemporalHeatmap() {
  const hm = document.getElementById('temporalHeatmap');
  if (!hm) return;
  // Header row
  let html = '<div style="font-size:9px;color:var(--grey);font-weight:700;display:contents">';
  // Zones x sessions grid (zone label + 3 session cells)
  // Use 4-col grid: zone label + S1 + S2 + S3
  hm.style.gridTemplateColumns = 'auto 1fr 1fr 1fr';
  html = '';
  // Header
  ['Zone','S1','S2','S3'].forEach(h => {
    html += `<div style="font-size:9px;font-weight:700;color:var(--grey);padding:2px 4px;text-align:center">${h}</div>`;
  });
  // Rows
  ZONES_HEALTH.slice(0,10).forEach((vals, zi) => {
    html += `<div style="font-size:9px;font-weight:700;color:var(--grey);padding:2px 4px;display:flex;align-items:center">${ZONE_LABELS_HM[zi]}</div>`;
    vals.forEach(v => {
      html += `<div class="thm-cell" style="background:${healthColor(v)}">${v}</div>`;
    });
  });
  hm.innerHTML = html;
}

