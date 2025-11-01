# test_googletrans.py
import sys
import socket

def print_header(title):
    print("=" * 60)
    print(title)
    print("=" * 60)

def check_package():
    print_header("1) Kiểm tra cài đặt package")
    try:
        from importlib.metadata import version, PackageNotFoundError  # Py3.8+
    except Exception:
        # Python cũ hơn
        version = None
        PackageNotFoundError = Exception

    try:
        import googletrans
        ver = "unknown"
        if version:
            try:
                ver = version("googletrans")
            except PackageNotFoundError:
                pass
        print(f"✅ Đã import 'googletrans' (version: {ver})")
        return True
    except Exception as e:
        print(f"❌ Chưa cài hoặc import lỗi: {type(e).__name__}: {e}")
        print("👉 Cài đặt đề xuất: pip install googletrans==4.0.0rc1")
        return False

def quick_network_check():
    print_header("2) Kiểm tra mạng (dns và outbound)")
    try:
        socket.gethostbyname("translate.googleapis.com")
        print("✅ DNS resolve OK (translate.googleapis.com)")
    except Exception as e:
        print(f"⚠️ DNS issue: {e}")
    # Không mở socket ra ngoài để tránh firewall khó chịu—chỉ check DNS là đủ

def try_translate():
    print_header("3) Thử dịch mẫu")
    try:
        from googletrans import Translator
        t = Translator()
        res = t.translate("hello world", dest="vi")
        print("✅ translate() OK")
        print(f"Input : 'hello world'\nOutput: '{res.text}' (dest={res.dest}, src={res.src})")
        return True
    except Exception as e:
        print(f"❌ translate() lỗi: {type(e).__name__}: {e}")
        print("Gợi ý:")
        print("- Đảm bảo dùng đúng bản: pip install googletrans==4.0.0rc1")
        print("- Nếu mạng qua proxy, set biến môi trường HTTPS_PROXY/HTTP_PROXY.")
        print("- Thử chạy lại vài lần vì google có thể rate-limit tạm thời.")
        return False

if __name__ == "__main__":
    ok_pkg = check_package()
    quick_network_check()
    ok_run = try_translate() if ok_pkg else False
    print_header("KẾT LUẬN")
    if ok_pkg and ok_run:
        print("🎉 googletrans HOẠT ĐỘNG BÌNH THƯỜNG.")
        sys.exit(0)
    elif ok_pkg and not ok_run:
        print("⚠️ ĐÃ CÀI googletrans nhưng translate() lỗi. Xem gợi ý ở trên.")
        sys.exit(2)
    else:
        print("❌ Chưa cài hoặc import lỗi. Cài đặt: pip install googletrans==4.0.0rc1")
        sys.exit(1)
