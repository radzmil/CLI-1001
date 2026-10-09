const $ = id => document.getElementById(id);
const profileTrigger = $('user-logo');
const profileDropdown = $('user-dropdown');
const mobileNavToggle = $('mobile-nav-toggle');
const mobileNavigation = $('mobile-navigation');
const humanReply = $('human-reply');
function closeMobileNavigation() {
  mobileNavigation.classList.remove('open');
  mobileNavToggle.setAttribute('aria-expanded', 'false');
}
mobileNavToggle.addEventListener('click', () => {
  const open = mobileNavigation.classList.toggle('open');
  mobileNavToggle.setAttribute('aria-expanded', String(open));
});
document.querySelectorAll('.sidebar .nav-item').forEach(link => {
  link.addEventListener('click', closeMobileNavigation);
});
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
  if (event.key === 'Escape' && mobileNavigation.classList.contains('open')) {
    closeMobileNavigation();
    mobileNavToggle.focus();
  }
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
  closeMobileNavigation();
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
  $('page-description').textContent = active === 'control-center' ? 'Aktiviti mesej sebenar daripada pangkalan data klien.' : titles[active] + ' · Portal klien';
  $('refresh').hidden = !['control-center', 'phonebook'].includes(active);
  if (active === 'control-center') refresh();
  if (active === 'phonebook') renderContacts();
  if (active === 'token-usage') loadTokenMessageActivity();
  if (active === 'token-usage') loadTokenUsage();
  if (active === 'settings') { loadSubscription(); loadCompany(); }
  if (active === 'bot-profile') loadBotProfile();
}
window.addEventListener('hashchange', activateTab);
let leads = [], selected = '', refreshing = false;
let contactPage = 0;
const contactsPerPage = 10;
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
function display(value) { return value == null ? '—' : String(value); }
async function postProfile(url, body) {
  const response = await fetch(url, {method: 'POST', credentials: 'same-origin', body,
    headers: body instanceof FormData ? {} : {'Content-Type': 'application/json'}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Gagal menyimpan.');
  return data;
}
function setLogo(url) {
  document.querySelectorAll('.company-logo, .dropdown-logo, .logo-preview').forEach(img => {
    img.src = url.startsWith('/api/profile/logo') ? url + '?v=' + Date.now() : url;
  });
}
async function loadCompany() {
  try {
    const data = await api('/api/profile/company');
    $('company-name').value = data.display_name;
    $('company-email').value = data.email;
    setLogo(data.logo_url);
  } catch (error) { $('company-feedback').textContent = error.message; }
}
$('company-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  $('company-feedback').textContent = 'Menyimpan...';
  try {
    await postProfile('/api/profile/company', JSON.stringify({display_name: $('company-name').value, email: $('company-email').value}));
    const file = $('company-logo').files[0];
    if (file) {
      const body = new FormData();
      body.append('logo', file);
      await postProfile('/api/profile/logo', body);
      $('company-logo').value = '';
    }
    await loadCompany();
    document.querySelectorAll('.sidebar-brand h2, .dropdown-header strong').forEach(el => { el.textContent = $('company-name').value; });
    document.querySelector('.dropdown-header small').textContent = $('company-email').value;
    $('company-feedback').textContent = 'Profil berjaya disimpan.';
  } catch (error) { $('company-feedback').textContent = error.message; }
  finally { button.disabled = false; }
});
$('password-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  if ($('new-password').value !== $('confirm-password').value) {
    $('password-feedback').textContent = 'Pengesahan kata laluan tidak sepadan.';
    return;
  }
  button.disabled = true;
  try {
    await postProfile('/api/profile/password', JSON.stringify({current_password: $('current-password').value,
      new_password: $('new-password').value, confirm_password: $('confirm-password').value}));
    form.reset();
    $('password-feedback').textContent = 'Kata laluan berjaya ditukar. Gunakan kata laluan baharu untuk log masuk seterusnya.';
  } catch (error) { $('password-feedback').textContent = error.message; }
  finally { button.disabled = false; }
});
async function loadTokenUsage() {
  try {
    const data = await api('/api/token-usage');
    for (const key of ['ai', 'meta']) {
      const quota = data[key];
      $(key + '-balance').textContent = display(quota.balance);
      $(key + '-quota').textContent = display(quota.quota);
      $(key + '-used').textContent = display(quota.used);
      $(key + '-progress').style.width = quota.percent == null ? '0%' : Math.max(0, Math.min(100, quota.percent)) + '%';
    }
    $('token-renewal').textContent = display(data.renewal_date);
    $('token-usage-status').textContent = '';
  } catch (error) { $('token-usage-status').textContent = error.message; }
}
async function loadSubscription() {
  try {
    const data = await api('/api/subscription');
    $('sub-plan').textContent = display(data.plan);
    $('sub-status').textContent = display(data.status);
    $('sub-renewal').textContent = display(data.renewal_date);
    $('sub-quota').textContent = display(data.token_quota);
    $('sub-price').textContent = data.price_rm == null ? 'Tidak direkodkan' : 'RM' + data.price_rm + '/bulan';
    $('subscription-status').textContent = '';
  } catch (error) { $('subscription-status').textContent = error.message; }
}
async function loadBotProfile() {
  try {
    const data = await api('/api/bot-profile');
    $('bot-name').value = data.bot_name || '';
    $('bot-phone').value = data.phone_number || '';
    $('bot-status').textContent = display(data.status);
    $('bot-storage').textContent = data.storage_used_mb == null || data.storage_max_mb == null
      ? 'Tidak direkodkan' : data.storage_used_mb + ' / ' + data.storage_max_mb + ' MB';
    $('bot-profile-status').textContent = '';
  } catch (error) { $('bot-profile-status').textContent = error.message; }
}
$('bot-profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  $('bot-profile-status').textContent = 'Menyimpan...';
  try {
    await postProfile('/api/bot-profile', JSON.stringify({bot_name: $('bot-name').value.trim()}));
    $('bot-profile-status').textContent = 'Nama bot berjaya disimpan.';
  } catch (error) { $('bot-profile-status').textContent = error.message; }
  finally { button.disabled = false; }
});
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
    button.onclick = () => { selected = lead.phone; humanReply.hidden = true; $('human-message').value = ''; $('contact-selected').textContent = lead.phone; contactName.disabled = false; saveName.disabled = false; contactName.value = lead.name || ''; $('contact-status').textContent = ''; renderLeads(); loadHistory(); loadChatMode(); };
  }
}
function renderContacts() {
  const box = $('contact-list'); box.replaceChildren();
  const term = $('contact-search').value.trim().toLowerCase();
  const matches = leads.filter(lead => (lead.phone + ' ' + lead.name).toLowerCase().includes(term));
  contactPage = Math.min(contactPage, Math.max(0, Math.ceil(matches.length / contactsPerPage) - 1));
  $('contact-empty').hidden = matches.length !== 0;
  $('contact-page').textContent = 'Halaman ' + (contactPage + 1) + ' / ' + Math.max(1, Math.ceil(matches.length / contactsPerPage));
  $('contact-prev').disabled = contactPage === 0;
  $('contact-next').disabled = (contactPage + 1) * contactsPerPage >= matches.length;
  for (const lead of matches.slice(contactPage * contactsPerPage, (contactPage + 1) * contactsPerPage)) {
    const row = add(box, 'tr', '');
    add(row, 'td', lead.name || 'Nama belum disimpan');
    add(row, 'td', lead.phone);
    add(row, 'td', 'Belum tersedia');
    add(row, 'td', 'Semak dalam chat');
    const cell = add(row, 'td', '');
    const button = add(cell, 'button', 'Pilih', 'secondary');
    button.type = 'button';
    button.onclick = () => { selected = lead.phone; contactName.disabled = false; saveName.disabled = false; contactName.value = lead.name || ''; $('contact-selected').textContent = lead.phone; $('contact-status').textContent = ''; renderContacts(); };
    const chat = add(cell, 'button', 'Lihat chat', 'secondary');
    chat.type = 'button';
    chat.onclick = () => { selected = lead.phone; location.hash = 'control-center'; renderLeads(); loadHistory(); loadChatMode(); };
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
async function loadChatMode() {
  const phone = selected;
  const button = $('takeover');
  button.disabled = true;
  humanReply.hidden = true;
  $('chat-mode-status').textContent = 'Menyemak mod perbualan...';
  try {
    const data = await api('/api/chat-mode?phone=' + encodeURIComponent(phone));
    if (selected !== phone) return;
    button.dataset.mode = data.mode;
    humanReply.hidden = data.mode !== 'human';
    button.textContent = data.mode === 'human' ? 'Serah semula kepada AI' : 'Ambil alih · Human Touch';
    $('chat-mode-status').textContent = data.mode === 'human'
      ? 'Human Touch aktif · bot tidak membalas automatik. Balas menggunakan nombor WhatsApp Business yang disambungkan.'
      : 'AI aktif · bot membalas secara automatik.';
    button.disabled = false;
  } catch (error) {
    if (selected === phone) $('chat-mode-status').textContent = error.message;
  }
}
$('takeover').onclick = async () => {
  const phone = selected;
  const button = $('takeover');
  const mode = button.dataset.mode === 'human' ? 'ai' : 'human';
  button.disabled = true;
  $('chat-mode-status').textContent = 'Menyimpan mod perbualan...';
  try {
    const response = await fetch('/api/chat-mode', {method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({phone, mode})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Gagal menukar mod perbualan.');
    if (selected === phone) await loadChatMode();
  } catch (error) {
    if (selected === phone) { $('chat-mode-status').textContent = error.message; button.disabled = false; }
  }
};
humanReply.addEventListener('submit', event => {
  event.preventDefault();
  const message = $('human-message').value.trim();
  const phone = selected.replace(/\D/g, '');
  if (!message || !phone || humanReply.hidden) return;
  window.open('https://wa.me/' + phone + '?text=' + encodeURIComponent(message), '_blank', 'noopener,noreferrer');
});
let activityChart;
function renderActivity(days) {
  const wrapper = $('daily-activity');
  wrapper.replaceChildren();
  if (activityChart) { activityChart.destroy(); activityChart = null; }
  if (!days) {
    add(wrapper, 'div', 'Data aktiviti tidak dapat dimuatkan.', 'empty-state');
    return;
  }
  if (!days.some(day => day.messages > 0)) {
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
  gradient.addColorStop(0, 'rgba(32,75,120,.18)');
  gradient.addColorStop(1, 'rgba(32,75,120,0)');
  activityChart = new Chart(canvas, {
    type: 'line',
    data: {labels: days.map(day => day.date), datasets: [{label: 'Mesej', data: days.map(day => day.messages),
      borderColor: '#204b78', backgroundColor: gradient, borderWidth: 2, fill: true, tension: .25,
      pointBackgroundColor: '#204b78', pointBorderColor: '#fff', pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6}]},
    options: {responsive: true, maintainAspectRatio: false,
      plugins: {legend: {display: false}, tooltip: {backgroundColor: '#17263d', titleColor: '#fff', bodyColor: '#e0e7ee'}},
      scales: {x: {grid: {display: false}, ticks: {color: '#64748b'}},
        y: {beginAtZero: true, grid: {color: '#e5eaf0'}, ticks: {color: '#64748b', precision: 0}}}}
  });
}
async function loadAnalytics() {
  try {
    const data = await api('/api/analytics');
    if (data.source !== 'messages') throw new Error('Sumber data analisis tidak dapat disahkan.');
    $('metric-prospects').textContent = data.prospects.toLocaleString('ms-MY');
    $('metric-incoming').textContent = data.incoming.toLocaleString('ms-MY');
    $('metric-replies').textContent = data.replies.toLocaleString('ms-MY');
    $('metric-week').textContent = data.messages_7d.toLocaleString('ms-MY');
    $('analytics-updated').textContent = 'Rekod mesej · dikemas kini ' + new Date(data.as_of).toLocaleString('ms-MY');
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
    renderActivity(null); $('top-leads').replaceChildren();
    add($('top-leads'), 'p', 'Data prospek tidak dapat dimuatkan.', 'empty-state');
  }
}
async function loadTokenMessageActivity() {
  const status = $('token-activity-status');
  const summary = $('token-message-summary');
  status.textContent = 'Memuatkan rekod mesej...';
  summary.hidden = true;
  try {
    const data = await api('/api/analytics');
    if (data.source !== 'messages') throw new Error('Sumber data tidak dapat disahkan.');
    $('token-incoming').textContent = data.incoming.toLocaleString('ms-MY');
    $('token-outgoing').textContent = data.replies.toLocaleString('ms-MY');
    $('token-week').textContent = data.messages_7d.toLocaleString('ms-MY');
    summary.hidden = false;
    status.textContent = 'Rekod mesej dikemas kini ' + new Date(data.as_of).toLocaleString('ms-MY');
  } catch (error) {
    status.textContent = 'Rekod mesej tidak tersedia: ' + error.message;
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  if (!location.hash || location.hash === '#control-center') loadAnalytics();
  if (location.hash === '#token-usage') loadTokenMessageActivity();
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
$('contact-search').oninput = () => { contactPage = 0; renderContacts(); };
$('contact-prev').onclick = () => { contactPage--; renderContacts(); };
$('contact-next').onclick = () => { contactPage++; renderContacts(); };
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
        if (notification.type === 'chat_changed') refresh();
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