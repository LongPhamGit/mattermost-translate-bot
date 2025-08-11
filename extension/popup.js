// popup.js
document.addEventListener('DOMContentLoaded', () => {
  const logList = document.getElementById('logList');
  const unreadInfo = document.getElementById('unreadInfo');
  const openFullBtn = document.getElementById('openFull');
  const clearBtn = document.getElementById('clearUnread');

  function render(logs, unread) {
    logList.innerHTML = '';
    unreadInfo.textContent = unread ? `Unread: ${unread}` : '';
    (logs || []).slice(0, 20).forEach(item => {
      const div = document.createElement('div');
      div.className = 'entry';
      div.innerHTML = `
        <div class="time">${item.time}</div>
        <div class="meta">@${item.user} in #${item.channel}</div>
        <div class="orig">💬 ${escapeHtml(item.original)}</div>
        <div class="trans">🈶 ${escapeHtml(item.translated)}</div>
      `;
      logList.appendChild(div);
    });
  }

  chrome.storage.local.get(['logs','unread'], (res) => {
    render(res.logs || [], res.unread || 0);
  });

  // listen to storage changes to update popup live
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && (changes.logs || changes.unread)) {
      chrome.storage.local.get(['logs','unread'], (res) => {
        render(res.logs || [], res.unread || 0);
      });
    }
  });

  openFullBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('log.html') });
  });

  clearBtn.addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'clearUnread' }, (resp) => {
      if (resp && resp.ok) {
        chrome.storage.local.set({ unread: 0 }, () => {
          render([], 0); // or re-fetch logs
        });
      }
    });
  });

  function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }
});
