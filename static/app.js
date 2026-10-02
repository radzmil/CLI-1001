const $ = id => document.getElementById(id);
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
  const matches = leads.filter(lead => lead.phone.includes($('search').value.trim()));
  if (!matches.length) add(box, 'p', 'Tiada perbualan lagi.');
  for (const lead of matches) {
    const button = add(box, 'button', lead.phone, 'lead' + (selected === lead.phone ? ' selected' : ''));
    button.type = 'button';
    button.onclick = () => { selected = lead.phone; renderLeads(); loadHistory(); };
  }
}
async function loadHistory() {
  const phone = selected;
  try {
    const messages = await api('/api/history?phone=' + encodeURIComponent(phone));
    if (selected !== phone) return;
    const header = $('chat-header'); header.replaceChildren();
    add(header, 'h2', 'Perbualan'); add(header, 'p', phone);
    const box = $('messages'); box.replaceChildren();
    if (!messages.length) add(box, 'p', 'Tiada mesej lagi.');
    for (const msg of messages) {
      const bubble = add(box, 'div', '', 'bubble ' + (msg.sender === 'customer' ? 'incoming' : 'outgoing'));
      add(bubble, 'div', msg.text); add(bubble, 'small', msg.time);
    }
    box.scrollTop = box.scrollHeight;
  } catch (error) { $('notice').textContent = error.message; }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    leads = await api('/api/leads');
    $('notice').textContent = '';
    renderLeads();
    if (selected) await loadHistory();
  } catch (error) { $('notice').textContent = error.message; }
  finally { refreshing = false; }
}
$('search').oninput = renderLeads;
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