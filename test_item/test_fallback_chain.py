# test_fallback_chain.py
import os
import sys

def header(t):
    print("\n" + "="*60)
    print(t)
    print("="*60)

header("0) Kiểm tra import module translate")
try:
    import translate
    print("✅ import translate OK")
    print("translate.py path:", translate.__file__)
except Exception as e:
    print("❌ Không import được translate:", type(e).__name__, e)
    sys.exit(1)

# Bật debug ẩn nếu bạn đang dùng bản translate.py có TRANSLATE_DEBUG
os.environ.setdefault("TRANSLATE_DEBUG", "true")

SAMPLE_TEXT = "hello world"
TARGET = "vi"

header("1) Gọi bình thường (nếu Gemini hoạt động sẽ thấy prefix 🔁 )")
try:
    out = translate.translate_with_fallback(SAMPLE_TEXT, TARGET)
    print("OUTPUT:", repr(out))
except Exception as e:
    print("❌ Lỗi:", type(e).__name__, e)

header("2) Giả lập Gemini lỗi để bắt buộc fallback sang googletrans")
# Monkeypatch tạm thời: ép Gemini trả rỗng -> rơi sang tầng 2
orig_gemini = translate.call_gemini_translate
try:
    translate.call_gemini_translate = lambda *a, **k: ""  # simulate fail/429
    out = translate.translate_with_fallback(SAMPLE_TEXT, TARGET)
    print("OUTPUT:", repr(out))
    if isinstance(out, str) and out.startswith("🌐 "):
        print("✅ Fallback sang googletrans thành công")
    else:
        print("⚠️ Không thấy prefix 🌐 . OUTPUT ở trên để bạn xem.")
finally:
    translate.call_gemini_translate = orig_gemini

header("3) (Tuỳ chọn) Giả lập TẤT CẢ đều lỗi để xem thông báo an toàn")
# Chỉ chạy nếu muốn xác nhận message fail-safe có hiển thị trong UI
orig_gt = getattr(translate, "_call_googletrans", None)
orig_lt = getattr(translate, "_call_libretranslate", None)
orig_mm = getattr(translate, "_call_mymemory", None)

try:
    if orig_gt: translate._call_googletrans = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gt fail"))
    if orig_lt: translate._call_libretranslate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("lt fail"))
    if orig_mm: translate._call_mymemory = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("mm fail"))

    # Đảm bảo không im lặng khi total failure:
    os.environ["TRANSLATE_RETURN_EMPTY_ON_TOTAL_FAILURE"] = "false"
    out = translate.translate_with_fallback(SAMPLE_TEXT, TARGET)
    print("OUTPUT:", repr(out))
    print("👉 Với UI lọc theo prefix, bạn có thể đặt TRANSLATE_FAILSAFE_PREFIX='🆓 ' để message thất bại vẫn hiển thị.")
finally:
    if orig_gt: translate._call_googletrans = orig_gt
    if orig_lt: translate._call_libretranslate = orig_lt
    if orig_mm: translate._call_mymemory = orig_mm

print("\nDone.")
