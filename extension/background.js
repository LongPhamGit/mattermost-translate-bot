let unreadCount = 0;
let serverUrl = "";
let token = "";

// Load config
chrome.storage.local.get(["serverUrl", "token"], (data) => {
  serverUrl = data.serverUrl || "";
  token = data.token || "";
  if (serverUrl && token) {
    connectSocket();
  }
});

function connectSocket() {
  const script = document.createElement("script");
  script.src = serverUrl + "/socket.io/socket.io.js";
  script.onload = () => {
    const socket = io(serverUrl);
    socket.on("new_message", (msg) => {
      unreadCount++;
      chrome.action.setBadgeText({ text: unreadCount.toString() });
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icon.png",
        title: `New message from ${msg.user}`,
        message: msg.text
      });
    });
  };
  document.head.appendChild(script);
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "register") {
    fetch(`${msg.serverUrl}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reg_code: msg.regCode })
    })
      .then(res => res.json())
      .then(data => {
        if (data.token) {
          chrome.storage.local.set({
            serverUrl: msg.serverUrl,
            token: data.token
          });
          serverUrl = msg.serverUrl;
          token = data.token;
          connectSocket();
          sendResponse({ success: true });
        } else {
          sendResponse({ success: false });
        }
      });
    return true;
  }
});
