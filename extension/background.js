let lastMessageId = null; // Lưu ID tin nhắn cuối cùng để tránh trùng lặp
const API_URL = "https://mattermost-translate-bot.onrender.com/translate"; // API của bạn

async function checkNewMessages() {
    try {
        const res = await fetch(API_URL);
        if (!res.ok) throw new Error("HTTP error " + res.status);

        const data = await res.json();
        if (!Array.isArray(data)) return;

        // Giả sử API trả về danh sách tin nhắn, mỗi tin có {id, translated}
        const newest = data[data.length - 1];
        
        if (newest && newest.id !== lastMessageId) {
            lastMessageId = newest.id;

            // Gửi thông báo
            chrome.notifications.create({
                type: "basic",
                iconUrl: "icon.png",
                title: "Tin nhắn mới",
                message: newest.translated || "Không có nội dung"
            });

            console.log("Tin mới:", newest.translated);
        }
    } catch (err) {
        console.error("Lỗi khi fetch tin nhắn:", err);
    }
}

// Chạy mỗi 5 giây
setInterval(checkNewMessages, 5000);

// Chạy ngay khi extension load
checkNewMessages();
