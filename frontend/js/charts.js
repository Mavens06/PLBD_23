function drawPhChart() {
  const canvas = document.getElementById('phHistChart');
  if (!canvas) return;
  canvas.width = canvas.offsetWidth;
  canvas.height = 80;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const values = APP_STATE.history.ph;
  const step = (W - 30) / (values.length - 1);

  ctx.clearRect(0, 0, W, H);
  ctx.strokeStyle = '#e8f5e9';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const y = 10 + ((H - 20) * i) / 3;
    ctx.beginPath();
    ctx.moveTo(15, y);
    ctx.lineTo(W - 10, y);
    ctx.stroke();
  }

  ctx.strokeStyle = '#2d6a35';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = 15 + i * step;
    const y = 10 + (H - 20) * (1 - (v - 5) / 3);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
