# Mattermost Translator Bot

Bot Flask đơn giản giúp dịch tin nhắn có mention `@pnblong` trong Mattermost sang tiếng Việt, ghi vào file log dưới dạng hội thoại và tự động mở log.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy bot

```bash
python app.py
```

## Cấu hình Mattermost

Tạo Outgoing Webhook với:

- Callback URL: `http://<ip-cua-ban>:5000/translate`
- Trigger word: `@pnblong` hoặc để trống để bắt mọi tin

## File log

Mỗi lần có tin nhắn được xử lý, nội dung sẽ được lưu vào `dialogue_log.txt` với định dạng đối thoại.

## Chạy như Windows Background Service (xem thêm bên dưới từ ChatGPT)
