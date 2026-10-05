const $ = id => document.getElementById(id);
const phoneBookLink = document.createElement('a');
phoneBookLink.href = '#phone-book';
phoneBookLink.textContent = '▣   Phone Book';
document.querySelector('aside nav').appendChild(phoneBookLink);
const phoneBook = document.createElement('div');
phoneBook.id = 'phone-book';
const phoneBookTitle = document.createElement('h2');
phoneBookTitle.textContent = 'Phone Book';
phoneBook.appendChild(phoneBookTitle);
const phoneBookDescription = document.createElement('p');
phoneBookDescription.textContent = 'Nama profil WhatsApp diisi automatik jika tersedia; nama manual tidak ditimpa.';
phoneBook.appendChild(phoneBookDescription);
const contactForm = document.createElement('form');
contactForm.id = 'contact-form';
const contactName = document.createElement('input');
contactName.id = 'contact-name';
contactName.placeholder = 'Nama prospek';
contactName.setAttribute('aria-label', 'Nama prospek');
contactName.maxLength = 150;
contactName.required = true;
contactName.disabled = true;
contactForm.appendChild(contactName);
const saveName = document.createElement('button');
saveName.type = 'submit';
saveName.disabled = true;
saveName.textContent = 'Simpan nama';
contactForm.appendChild(saveName);
phoneBook.appendChild(contactForm);
const contactStatus = document.createElement('p');
contactStatus.id = 'contact-status';
contactStatus.setAttribute('role', 'status');
phoneBook.appendChild(contactStatus);
document.getElementById('leads').after(phoneBook);
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
  if (!matches.length) add(box, 'p', 'Tiada perbualan lagi.');
  for (const lead of matches) {
    const button = add(box, 'button', (lead.name ? lead.name + ' · ' : '') + lead.phone, 'lead' + (selected === lead.phone ? ' selected' : ''));
    button.type = 'button';
    button.onclick = () => { selected = lead.phone; contactName.disabled = false; saveName.disabled = false; $('contact-name').value = lead.name || ''; $('contact-status').textContent = ''; renderLeads(); loadHistory(); };
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
async function loadAnalytics() {
  try {
    const data = await api('/api/analytics');
    $('metric-prospects').textContent = data.prospects.toLocaleString('ms-MY');
    $('metric-incoming').textContent = data.incoming.toLocaleString('ms-MY');
    $('metric-replies').textContent = data.replies.toLocaleString('ms-MY');
    $('metric-week').textContent = data.messages_7d.toLocaleString('ms-MY');
    $('analytics-updated').textContent = 'Dikemas kini ' + new Date(data.as_of).toLocaleString('ms-MY');
    const daily = $('daily-activity'); daily.replaceChildren();
    const max = Math.max(1, ...data.daily.map(day => day.messages));
    for (const day of data.daily) {
      const row = add(daily, 'div', '', 'activity-row');
      add(row, 'span', day.date);
      const track = add(row, 'div', '', 'activity-track');
      const bar = add(track, 'div', '', 'activity-bar');
      bar.style.width = (day.messages / max * 100) + '%';
      add(row, 'strong', day.messages);
    }
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
    $('daily-activity').replaceChildren(); $('top-leads').replaceChildren();
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  loadAnalytics();
  try {
    leads = await api('/api/leads');
    $('notice').textContent = '';
    renderLeads();
    if (selected) await loadHistory();
  } catch (error) { $('notice').textContent = error.message; }
  finally { refreshing = false; }
}
$('search').oninput = renderLeads;
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
    $('contact-status').textContent = 'Nama disimpan.';
    await loadHistory();
  } catch (error) { $('contact-status').textContent = error.message; }
};
$('refresh').onclick = refresh;
refresh();
let socket, retryDelay = 1000, reconnectTimer;
async function connectChat() {
  if (document.visibilityState !== 'visible') return;
  try {
    const {url, ticket} = await api('/api/chat-ticket');
    if (document.visibilityState !== 'visible') return;
    const endpoint = new URL(url);
    endpoint.searchParams.set('ticket', ticket);
    const current = new WebSocket(endpoint.href);
    socket = current;
    current.onopen = () => { retryDelay = 1000; refresh(); };
    current.onmessage = event => { if (event.data === 'refresh') refresh(); };
    current.onerror = () => current.close();
    current.onclose = () => { if (socket === current) reconnect(); };
  } catch (error) { $('notice').textContent = error.message; reconnect(); }
}
function reconnect() {
  if (document.visibilityState !== 'visible' || reconnectTimer) return;
  reconnectTimer = setTimeout(() => { reconnectTimer = null; connectChat(); }, retryDelay);
  retryDelay = Math.min(retryDelay * 2, 30000);
}
connectChat();
// Fallback also recovers notifications missed during reconnects.
setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 5000);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') { refresh(); if (!socket || socket.readyState === WebSocket.CLOSED) connectChat(); }
  else { clearTimeout(reconnectTimer); reconnectTimer = null; if (socket) socket.close(); }
});