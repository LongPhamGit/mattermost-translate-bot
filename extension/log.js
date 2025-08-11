// log.js
function renderLogs(list) {
  const container = document.getElementById('fullLog');
  container.innerHTML = '';
  (list || []).forEach(item => {
    const div = document.createElement('div');
    div.className = 'logEntry';
    div.innerHTML = `
      <div class="time">${item.time}</div>
      <div class="meta">@${item.user} in #${item.channel}</div>
      <div class="orig">💬 ${escapeHtml(item.original)}</div>
      <div class="trans">🈶 ${escapeHtml(item.translated)}</div>
    `;
    container.appendChild(div);
  });
}

function escapeHtml(s) {
  if (!s) return '';
  return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

document.addEventListener('DOMContentLoaded', () => {
  chrome.storage.local.get('logs', (res) => {
    renderLogs(res.logs || []);
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.logs) {
      renderLogs(changes.logs.newValue || []);
    }
  });
});
