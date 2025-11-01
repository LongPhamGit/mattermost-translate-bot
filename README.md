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

## Đóng gói thành file `.exe`

Ứng dụng đã được cấu hình sẵn để đóng gói bằng [PyInstaller](https://pyinstaller.org/) với file spec đi kèm. Các bước thực hiện trên Windows:

1. Cài các phụ thuộc cần thiết (bao gồm `PyQt6`, `PyQt6-WebEngine`, `pyinstaller`).
2. Mở Command Prompt và chạy:

   ```bat
   build.bat path\to\your\config.json
   ```

   - Tham số cấu hình là tùy chọn. Nếu bỏ trống, script sẽ tìm `config.json` trong thư mục hiện tại.
   - Sau khi build xong, file `MattermostChecker.exe` nằm trong thư mục `dist`. Script cũng sẽ tự động sao chép file cấu hình vào cùng thư mục để chương trình có thể chạy ngay.

Khi chạy file exe, bạn có thể thay đổi vị trí file cấu hình bằng cách đặt `config.json` cạnh file exe hoặc đặt biến môi trường `MATTERMOST_TRANSLATE_CONFIG` trỏ tới vị trí mong muốn.
