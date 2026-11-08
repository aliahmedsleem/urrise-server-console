(() => {
  const $ = (id) => document.getElementById(id);
  const label = (value) => String(value ?? 'Unknown');
  const formatTime = (value) => {
    const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + 'Z';
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  };
  function serviceCard(service) {
    const article = document.createElement('article');
    article.className = 'monitor-service';
    const details = document.createElement('div');
    const title = document.createElement('b');
    title.textContent = label(service.label);
    const name = document.createElement('small');
    name.textContent = label(service.name);
    details.append(title, name);
    const state = document.createElement('span');
    state.className = 'monitor-state ' + (service.status === 'active' ? 'is-up' : 'is-down');
    state.textContent = label(service.status);
    article.append(details, state);
    return article;
  }
  function eventRow(event) {
    const article = document.createElement('article');
    article.className = 'monitor-event';
    const details = document.createElement('div');
    const title = document.createElement('b');
    title.textContent = event.metric === 'service' ? label(event.target) : label(event.metric) + (event.target ? ' · ' + event.target : '');
    const time = document.createElement('small');
    time.textContent = formatTime(event.created_at);
    details.append(title, time);
    const status = document.createElement('strong');
    const level = ['critical', 'warning', 'recovered'].includes(event.level) ? event.level : '';
    status.className = level;
    status.textContent = label(event.level).toUpperCase() + (event.metric === 'service' || event.level === 'recovered' ? '' : ' · ' + Number(event.value).toFixed(1) + label(event.unit));
    article.append(details, status);
    return article;
  }
  async function refresh() {
    try {
      const response = await fetch('/api/monitoring', {credentials:'same-origin',cache:'no-store'});
      if (!response.ok) throw new Error('Monitoring data unavailable (' + response.status + ')');
      const data = await response.json();
      const services = data.services || [];
      const events = data.events || [];
      $('monitor-total').textContent = services.length;
      $('monitor-running').textContent = services.filter(s => s.status === 'active').length;
      $('monitor-down').textContent = services.filter(s => s.status !== 'active').length;
      $('monitor-incidents').textContent = events.filter(e => e.level === 'critical' || e.level === 'warning').length;
      $('monitor-services').replaceChildren(...services.map(serviceCard));
      if (events.length) $('monitor-events').replaceChildren(...events.map(eventRow));
      else $('monitor-events').textContent = 'No incidents recorded yet.';
      $('monitor-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    } catch (error) {
      $('monitor-updated').textContent = error.message;
    }
  }
  $('monitor-reload').addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 30000);
})();