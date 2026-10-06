const $ = id => document.getElementById(id);
const profileTrigger = $('user-logo');
const profileDropdown = $('user-dropdown');
function closeProfileMenu() {
  profileDropdown.hidden = true;
  profileTrigger.setAttribute('aria-expanded', 'false');
}
profileTrigger.addEventListener('click', () => {
  profileDropdown.hidden = !profileDropdown.hidden;
  profileTrigger.setAttribute('aria-expanded', String(!profileDropdown.hidden));
});
document.addEventListener('click', event => {
  if (!event.target.closest('.user-menu')) closeProfileMenu();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !profileDropdown.hidden) {
    closeProfileMenu();
    profileTrigger.focus();
  }
});
document.querySelectorAll('[data-profile-target]').forEach(link => {
  link.addEventListener('click', () => {
    closeProfileMenu();
    // hashchange reveals the settings panel before moving focus.
    setTimeout(() => { activateTab(); $(link.dataset.profileTarget).focus(); }, 0);
  });
});
const contactName = $('contact-name');
const saveName = document.querySelector('#contact-form button');
const tabs = ['control-center', 'phonebook', 'bot-profile', 'token-usage', 'settings'];
const titles = {'control-center': 'Pusat Kawalan', phonebook: 'Phone Book', 'bot-profile': 'Profil Bot', 'token-usage': 'Penggunaan Token', settings: 'Tetapan'};
function activateTab() {
  const requested = location.hash.slice(1);
  const active = tabs.includes(requested) ? requested : 'control-center';
  for (const tab of tabs) {
    const panel = $('tab-' + tab);
    panel.hidden = tab !== active;
    panel.classList.toggle('active', tab === active);
  }
  document.querySelectorAll('.nav-item').forEach(link => {
    link.classList.toggle('active', link.dataset.tab === active);
    if (link.dataset.tab === active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  $('page-title').textContent = titles[active];
  if ($('current-tab')) $('current-tab').textContent = titles[active];
  $('page-description').textContent = active === 'control-center' ? 'Perbualan, analisis dan WhatsApp lead Architech Systems.' : titles[active] + ' · Architech Systems';
  $('refresh').hidden = !['control-center', 'phonebook'].includes(active);
  if (active === 'control-center') refresh();
  if (active === 'phonebook') renderContacts();
}
window.addEventListener('hashchange', activateTab);
let leads = [], selected = '', refreshing = false;
function add(parent, tag, content, cls = '') {
  const el = document.createElement(tag);
  el.textContent = content == null ? '' : String(content);
  el.className = cls;
  parent.appendChild(el);
  return el;
}
async function api(url) {
  const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Permintaan gagal.');
  return data;
}
function renderLeads() {
  const box = $('leads'); box.replaceChildren();
  const matches = leads.filter(lead => (lead.phone + ' ' + lead.name).toLowerCase().includes($('search').value.trim().toLowerCase()));
  if (!matches.length) add(box, 'p', 'Tiada perbualan lagi. Data akan muncul apabila mesej masuk.', 'empty-state');
  for (const lead of matches) {
    const button = add(box, 'button', '', 'lead lead-card' + (selected === lead.phone ? ' selected' : ''));
    add(button, 'span', (lead.name || lead.phone).trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase(), 'lead-avatar');
    const info = add(button, 'span', '', 'lead-info');
    add(info, 'span', lead.name || 'Nama belum disimpan', 'lead-name');
    add(info, 'span', lead.phone, 'lead-phone');
    button.type = 'button';
    button.onclick = () => { selected = lead.phone; $('contact-selected').textContent = lead.phone; contactName.disabled = false; saveName.disabled = false; contactName.value = lead.name || ''; $('contact-status').textContent = ''; renderLeads(); loadHistory(); };
  }
}
function renderContacts() {
  const box = $('contact-list'); box.replaceChildren();
  const term = $('contact-search').value.trim().toLowerCase();
  const matches = leads.filter(lead => (lead.phone + ' ' + lead.name).toLowerCase().includes(term));
    if (!matches.length) add(box, 'p', 'Tiada kontak ditemui.', 'empty-state');
  for (const lead of matches) {
    const button = add(box, 'button', (lead.name ? lead.name + ' · ' : '') + lead.phone, 'lead' + (selected === lead.phone ? ' selected' : ''));
    button.type = 'button';
    button.onclick = () => { selected = lead.phone; contactName.disabled = false; saveName.disabled = false; contactName.value = lead.name || ''; $('contact-selected').textContent = lead.phone; $('contact-status').textContent = ''; renderContacts(); };
  }
}
async function loadHistory() {
  const phone = selected;
  try {
    const messages = await api('/api/history?phone=' + encodeURIComponent(phone));
    if (selected !== phone) return;
    const header = $('chat-header'); header.replaceChildren();
    add(header, 'h2', 'Perbualan'); add(header, 'p', (leads.find(lead => lead.phone === phone)?.name || 'Nama belum disimpan') + ' · ' + phone);
    const box = $('messages'); box.replaceChildren();
    if (!messages.length) add(box, 'p', 'Tiada mesej lagi.');
    for (const msg of messages) {
      const bubble = add(box, 'div', '', 'bubble ' + (msg.sender === 'customer' ? 'incoming' : 'outgoing'));
      add(bubble, 'div', msg.text); add(bubble, 'small', msg.time);
    }
    box.scrollTop = box.scrollHeight;
  } catch (error) { $('notice').textContent = error.message; }
}
let activityChart;
function renderActivity(days) {
  const wrapper = $('daily-activity');
  wrapper.replaceChildren();
  if (activityChart) { activityChart.destroy(); activityChart = null; }
  if (!days || !days.some(day => day.messages > 0)) {
    add(wrapper, 'div', 'Tiada aktiviti direkodkan. Data akan muncul apabila ada mesej masuk.', 'empty-state');
    return;
  }
  if (typeof Chart === 'undefined') {
    const max = Math.max(1, ...days.map(day => day.messages));
    for (const day of days) {
      const row = add(wrapper, 'div', '', 'activity-row');
      add(row, 'span', day.date);
      const track = add(row, 'div', '', 'activity-track');
      add(track, 'div', '', 'activity-bar').style.width = (day.messages / max * 100) + '%';
      add(row, 'strong', day.messages);
    }
    return;
  }
  const canvas = document.createElement('canvas');
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', 'Aktiviti mesej tujuh hari: ' + days.map(day => day.date + ': ' + day.messages).join(', '));
  wrapper.appendChild(canvas);
  const gradient = canvas.getContext('2d').createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(59,130,246,.32)');
  gradient.addColorStop(1, 'rgba(59,130,246,0)');
  activityChart = new Chart(canvas, {
    type: 'line',
    data: {labels: days.map(day => day.date), datasets: [{label: 'Mesej', data: days.map(day => day.messages),
      borderColor: '#3b82f6', backgroundColor: gradient, borderWidth: 2, fill: true, tension: .4,
      pointBackgroundColor: '#3b82f6', pointBorderColor: '#111827', pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6}]},
    options: {responsive: true, maintainAspectRatio: false,
      plugins: {legend: {display: false}, tooltip: {backgroundColor: '#1f2937', titleColor: '#f9fafb', bodyColor: '#9ca3af'}},
      scales: {x: {grid: {display: false}, ticks: {color: '#9ca3af'}},
        y: {beginAtZero: true, grid: {color: '#293244'}, ticks: {color: '#9ca3af', precision: 0}}}}
  });
}
async function loadAnalytics() {
  try {
    const data = await api('/api/analytics');
    $('metric-prospects').textContent = data.prospects.toLocaleString('ms-MY');
    $('metric-incoming').textContent = data.incoming.toLocaleString('ms-MY');
    $('metric-replies').textContent = data.replies.toLocaleString('ms-MY');
    $('metric-week').textContent = data.messages_7d.toLocaleString('ms-MY');
    $('analytics-updated').textContent = 'Dikemas kini ' + new Date(data.as_of).toLocaleString('ms-MY');
    renderActivity(data.daily);
    const top = $('top-leads'); top.replaceChildren();
    if (!data.top_leads.length) add(top, 'p', 'Belum ada mesej prospek.');
    for (const lead of data.top_leads) {
      const row = add(top, 'div', '', 'top-lead');
      add(row, 'span', lead.phone);
      add(row, 'small', lead.incoming + ' masuk · ' + lead.replies + ' balasan');
    }
  } catch (error) {
    $('analytics-updated').textContent = error.message;
    for (const id of ['metric-prospects', 'metric-incoming', 'metric-replies', 'metric-week']) $(id).textContent = '—';
    renderActivity([]); $('top-leads').replaceChildren();
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  if (!location.hash || location.hash === '#control-center') loadAnalytics();
  try {
    leads = await api('/api/leads');
    $('notice').textContent = '';
    renderLeads();
    renderContacts();
    if (selected) await loadHistory();
  } catch (error) { $('notice').textContent = error.message; }
  finally { refreshing = false; }
}
$('search').oninput = renderLeads;
$('contact-search').oninput = renderContacts;
$('contact-form').onsubmit = async event => {
  event.preventDefault();
  if (!selected) return;
  try {
    const response = await fetch('/api/contacts', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({phone: selected, name: $('contact-name').value.trim()})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Gagal menyimpan nama.');
    const lead = leads.find(item => item.phone === selected);
    if (lead) lead.name = data.name;
    renderLeads();
    renderContacts();
    $('contact-status').textContent = 'Nama disimpan.';
    await loadHistory();
  } catch (error) { $('contact-status').textContent = error.message; }
};
$('refresh').onclick = refresh;
refresh();
activateTab();
let socket, retryDelay = 1000, reconnectTimer, connecting = false;
async function connectChat() {
  if (document.visibilityState !== 'visible' || connecting ||
      (socket && socket.readyState !== WebSocket.CLOSED)) return;
  connecting = true;
  try {
    const {url, ticket} = await api('/api/chat-ticket');
    if (document.visibilityState !== 'visible') return;
    const endpoint = new URL(url);
    endpoint.searchParams.set('ticket', ticket);
    const current = new WebSocket(endpoint.href);
    socket = current;
    current.onopen = () => { retryDelay = 1000; refresh(); };
    current.onmessage = event => {
      if (event.data === 'refresh') { refresh(); return; }
      try {
        const notification = JSON.parse(event.data);
        if (notification.type === 'chat_changed' && notification.client_id === 'architechsystems') refresh();
      } catch (_) { /* Ignore heartbeat and malformed notifications. */ }
    };
    current.onerror = () => current.close();
    current.onclose = () => { if (socket === current) reconnect(); };
  } catch (error) { $('notice').textContent = error.message; }
  finally { connecting = false; if (!socket || socket.readyState === WebSocket.CLOSED) reconnect(); }
}
function reconnect() {
  if (document.visibilityState !== 'visible' || reconnectTimer || connecting) return;
  reconnectTimer = setTimeout(() => { reconnectTimer = null; connectChat(); }, retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30000);
}
connectChat();
// Fallback also recovers notifications missed during reconnects.
setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 5000);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') { refresh(); if (!socket || socket.readyState === WebSocket.CLOSED) connectChat(); }
  else { clearTimeout(reconnectTimer); reconnectTimer = null; if (socket) { const current = socket; socket = null; current.close(); } }
});