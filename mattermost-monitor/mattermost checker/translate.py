import requests
from config_loader import API_KEY, GEMINI_URL

def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return ""
    prompt_text = f"Dịch sang tiếng {target_language}, giữ nguyên ý nghĩa: {text}"
    headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return "🔁 " + data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return "[Lỗi dịch]"
