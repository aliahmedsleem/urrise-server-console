(() => {
  const root = document.getElementById('alert-events');
  if (!root) return;
  async function refreshAlerts() {
    try {
      const response = await fetch('/api/alerts', {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw Error('Alerts unavailable');
      const rows = await response.json();
      root.replaceChildren();
      if (!rows.length) { root.textContent = 'No alerts recorded yet.'; return; }
      for (const item of rows.slice(0, 12)) {
        const line = document.createElement('div');
        const label = document.createElement('span');
        const value = document.createElement('b');
        label.textContent = new Date(item.created_at).toLocaleString() + ' · ' + item.metric + (item.target ? ' ' + item.target : '');
        value.textContent = item.level === 'recovered' ? 'Recovered' : item.level.toUpperCase() + ' · ' + Number(item.value).toFixed(1) + item.unit;
        line.append(label, value);
        root.append(line);
      }
    } catch (e) { root.textContent = e.message; }
  }
  refreshAlerts();
  setInterval(refreshAlerts, 30000);
})();
