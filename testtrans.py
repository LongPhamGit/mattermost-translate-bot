# test_libretranslate_public.py
import os, sys, json
from textwrap import shorten

SAMPLE_TEXT = os.getenv("LT_SAMPLE_TEXT", "hello world")
TARGET_LANG = os.getenv("LT_TARGET_LANG", "vi")  # vi | en | ja | id ...
TIMEOUT     = float(os.getenv("FREE_TRANSLATE_TIMEOUT", "12"))

def sep(t): 
    print("\n" + "="*70 + f"\n{t}\n" + "="*70)

def parse_endpoints() -> list[str]:
    urls = []
    csv = os.getenv("LIBRETRANSLATE_URLS", "")
    if csv:
        urls += [u.strip() for u in csv.split(",") if u.strip()]
    single = os.getenv("FREE_TRANSLATE_URL", "")
    if single and single not in urls:
        urls.append(single)
    # fallback mặc định (public). Có thể lúc nào đó down/chặn SSL.
    if not urls:
        urls = [
            "https://libretranslate.de/translate",
            "https://libretranslate.com/translate",
            "https://translate.astian.org/translate",
            "https://lt.vern.cc/translate",
        ]
    # dedup
    seen = set(); out = []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def run():
    import requests

    sep("Config")
    endpoints = parse_endpoints()
    api_key   = os.getenv("FREE_TRANSLATE_API_KEY")  # thường không cần với public
    verify = True
    if os.getenv("FREE_TRANSLATE_VERIFY", "true").lower() == "false":
        verify = False
    ca_bundle = os.getenv("FREE_TRANSLATE_CA_BUNDLE")  # path .pem nếu có CA nội bộ
    if ca_bundle:
        verify = ca_bundle

    print("SAMPLE_TEXT            :", repr(SAMPLE_TEXT))
    print("TARGET_LANG            :", TARGET_LANG)
    print("LIBRETRANSLATE_URLS    :", os.getenv("LIBRETRANSLATE_URLS", "<unset>"))
    print("FREE_TRANSLATE_URL     :", os.getenv("FREE_TRANSLATE_URL", "<unset>"))
    print("FREE_TRANSLATE_API_KEY :", "set" if api_key else "unset")
    print("FREE_TRANSLATE_TIMEOUT :", TIMEOUT)
    print("FREE_TRANSLATE_VERIFY  :", os.getenv("FREE_TRANSLATE_VERIFY", "true"))
    print("FREE_TRANSLATE_CA_BUNDLE:", os.getenv("FREE_TRANSLATE_CA_BUNDLE", "<unset>"))
    print("Endpoints              :", endpoints)

    sep("Testing endpoints")
    ok_any = False
    for i, url in enumerate(endpoints, 1):
        print(f"\n[{i}/{len(endpoints)}] {url}")
        payload = {
            "q": SAMPLE_TEXT,
            "source": "auto",
            "target": TARGET_LANG,
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key

        try:
            r = requests.post(url, json=payload, timeout=TIMEOUT, verify=verify)
            print("HTTP:", r.status_code)
            # in vài header hữu ích nếu có
            for hk in ("retry-after","x-ratelimit-limit","x-ratelimit-remaining"):
                if hk in r.headers:
                    print(f"{hk}: {r.headers[hk]}")
            if r.status_code >= 400:
                print("Body:", shorten(r.text, width=240))
                continue

            # parse JSON
            try:
                data = r.json()
            except Exception:
                print("Non-JSON:", shorten(r.text, width=240))
                continue

            out = (data.get("translatedText") or data.get("translation") or "").strip()
            if out:
                print("✅ OK")
                print("Input :", SAMPLE_TEXT)
                print("Output:", out)
                ok_any = True
                break
            else:
                print("⚠️  JSON không có translatedText:", json.dumps(data)[:240])
        except Exception as e:
            print("⚠️ ", type(e).__name__, ":", e)

    sep("Kết luận")
    if ok_any:
        print("✅ Ít nhất một public endpoint hoạt động. Bạn có thể dùng LibreTranslate mà không cần tự host.")
        print("- Đưa URL/CSV vào ENV để app ưu tiên endpoint ổn định:")
        print("  LIBRETRANSLATE_URLS=", ",".join(endpoints))
    else:
        print("❌ Tất cả endpoint thử nghiệm đều lỗi.")
        print("Cách khắc phục nhanh:")
        print("  1) Cài certifi & trỏ Requests dùng CA chuẩn:")
        print("     pip install -U certifi")
        print("     set SSL_CERT_FILE=(python -c \"import certifi;print(certifi.where())\")")
        print("     set REQUESTS_CA_BUNDLE=%SSL_CERT_FILE%")
        print("  2) (Tạm test) tắt verify: set FREE_TRANSLATE_VERIFY=false")
        print("  3) Dùng endpoint khác hoặc tự host Docker: libretranslate/libretranslate")

if __name__ == "__main__":
    run()
