# translate.py
import os
import re
import requests
from config_loader import API_KEY, GEMINI_URL

# ======= Fallback config (có thể override bằng ENV) =======
FREE_TRANSLATE_URL = os.environ.get("FREE_TRANSLATE_URL", "https://libretranslate.de/translate")
FREE_TRANSLATE_API_KEY = os.environ.get("FREE_TRANSLATE_API_KEY", None)
FREE_TRANSLATE_TIMEOUT = float(os.environ.get("FREE_TRANSLATE_TIMEOUT", "12"))

# Thử import googletrans (không bắt buộc)
_HAVE_GOOGLETRANS = False
try:
    from googletrans import Translator as _GT_Translator  # pip install googletrans==4.0.0rc1
    _GT = _GT_Translator()
    _HAVE_GOOGLETRANS = True
except Exception:
    _HAVE_GOOGLETRANS = False

# Chuẩn hoá mã ngôn ngữ
_LANG_MAP = {
    "vi": "vi",
    "en": "en",
    "ja": "ja",
    "id": "id",
}
_LANG_NAME = {
    "vi": "Vietnamese",
    "en": "English",
    "ja": "Japanese",
    "id": "Indonesian",
}
def _norm_lang(code: str) -> str:
    return _LANG_MAP.get((code or "vi").lower(), "vi")


# ======= Helpers =======
def _build_translate_prompt(tgt_name: str, text: str) -> str:
    """
    Prompt: dịch sang {tgt_name}, không giải thích; nếu input là Markdown thì giữ NGUYÊN định dạng.
    """
    return (
        f"Translate the text below into {tgt_name}. Do not add any explanations or extra words. "
        "If the input contains Markdown, preserve its formatting EXACTLY as-is (headings, lists, bold/italic, code blocks, tables, inline code, links, spacing, and line breaks). "
        f"If the input is not Markdown, output clear {tgt_name} with appropriate punctuation and line breaks.\n\n"
        "INPUT:\n"
        f"{text}\n\n"
        f"OUTPUT ({tgt_name} only):"
    )

def _strip_fences(s: str) -> str:
    """Nếu output được bao bằng ```...```, bỏ hàng rào để tránh render dư."""
    s = s.strip()
    if s.startswith("```") and s.endswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return s

def _repair_markdown_structure(src: str, out: str) -> str:
    """
    Vá nhẹ khi model vẫn gộp list thành 1 dòng.
    """
    src_lines = [ln.rstrip() for ln in (src or "").splitlines()]

    def _is_bullet(ln: str) -> bool:
        ln = ln.lstrip()
        return (
            ln.startswith(("-", "*", "+"))
            or bool(re.match(r"^\d+\.\s", ln))
        )

    had_bullets = sum(1 for ln in src_lines if _is_bullet(ln)) >= 2

    if had_bullets and ("\n" not in out):
        reps = [
            (" - ", "\n- "),
            (" • ", "\n- "),
            (" ・", "\n- "),
            (" + ", "\n+ "),
            (" * ", "\n* "),
        ]
        for a, b in reps:
            if a in out:
                out = out.replace(a, b)

        out = re.sub(r"\s(\d+\.\s)", r"\n\1", out)

    return out


# ========== Primary: Gemini ==========
def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    """
    Dịch bằng Gemini. Nếu thành công → trả về có prefix '🔁 '.
    Nếu lỗi → trả về '[Lỗi dịch]' (nội bộ), translate_with_fallback sẽ KHÔNG hiển thị chuỗi này.
    """
    if not API_KEY or not GEMINI_URL:
        return "[Translate ERROR]"

    tgt_code = _norm_lang(target_language)
    tgt_name = _LANG_NAME.get(tgt_code, "Vietnamese")

    prompt_text = _build_translate_prompt(tgt_name, text)

    headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt_text}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topK": 1,
            "topP": 0.9,
            "response_mime_type": "text/markdown"
        }
    }
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        out = _strip_fences(out)
        out = _repair_markdown_structure(text, out)

        # Nếu output giống hệt input -> coi như lỗi để fallback
        #if out.replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", ""):
         #   return "[Lỗi dịch]"

        return "🔁 " + out
    except Exception:
        try:
            payload.pop("generationConfig", None)
            resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            out = _strip_fences(out)
            out = _repair_markdown_structure(text, out)

            #if out.replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", ""):
             #   return "[Lỗi dịch]"

            return "🔁 " + out
        except Exception as e:
             return f"[Translate ERROR] {e}"


# ========== Secondary: googletrans ==========
def _call_googletrans(text: str, target_language: str) -> str:
    if not _HAVE_GOOGLETRANS:
        raise RuntimeError("googletrans not installed")
    dest = _norm_lang(target_language)
    result = _GT.translate(text, dest=dest)
    out = (result.text or "").strip()
    if not out:
        raise RuntimeError("googletrans returned empty")
    return out


# ========== Tertiary: LibreTranslate ==========
def _call_libretranslate(text: str, target_language: str) -> str:
    if not FREE_TRANSLATE_URL:
        raise RuntimeError("FREE_TRANSLATE_URL is not set")
    tgt = _norm_lang(target_language)
    payload = {
        "q": text,
        "source": "auto",
        "target": tgt,
        "format": "text",
    }
    if FREE_TRANSLATE_API_KEY:
        payload["api_key"] = FREE_TRANSLATE_API_KEY

    r = requests.post(FREE_TRANSLATE_URL, json=payload, timeout=FREE_TRANSLATE_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out = (data.get("translatedText") or data.get("translation") or "").strip()
    if not out:
        raise RuntimeError("LibreTranslate returned empty")
    return out


# ========== Public API: dịch với fallback ==========
def translate_with_fallback(text: str, target_language: str = "vi") -> str:
    """
    Chuỗi fallback:
        1) Gemini (prefix 🔁)
        2) googletrans (prefix 🌐)
        3) LibreTranslate (prefix 🆓)
    KHÔNG bao giờ trả về chuỗi "[Lỗi dịch]" ra ngoài; nếu tất cả đều lỗi -> trả rỗng.
    """
    text = text or ""
    if not text.strip():
        return ""

    # 1) Gemini
    try:
        g = call_gemini_translate(text, target_language=target_language)
        # CHỈ nhận Gemini nếu có prefix thành công "🔁 "
        if isinstance(g, str) and g.startswith("🔁 "):
            return g
    except Exception:
        pass

    # 2) googletrans
    try:
        gt = _call_googletrans(text, target_language)
        if gt:
            gt = _repair_markdown_structure(text, gt)
            return "🌐 " + gt
    except Exception:
        pass

    # 3) LibreTranslate
    try:
        lt = _call_libretranslate(text, target_language)
        if lt:
            lt = _repair_markdown_structure(text, lt)
            return "🆓 " + lt
    except Exception:
        pass

    return ""
