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
_LANG_MAP = {"vi": "vi", "en": "en", "ja": "ja", "id": "id"}
_LANG_NAME = {"vi": "Vietnamese", "en": "English", "ja": "Japanese", "id": "Indonesian"}
def _norm_lang(code: str) -> str:
    return _LANG_MAP.get((code or "vi").lower(), "vi")

# ---------- Markdown protect/restore helpers ----------
_CODEBLOCK_RE = re.compile(r"```.*?```", flags=re.DOTALL)
_INLINECODE_RE = re.compile(r"`[^`\n]+`")
_URL_RE = re.compile(r"(?P<u>https?://\S+)")

def _protect_markdown(text: str):
    """
    Thay thế code block, inline code, URL bằng placeholder để máy dịch không đụng vào.
    Trả về (text_mới, mapping_dict)
    """
    mapping = {}
    idx = 0

    def repl_cb(m, tag):
        nonlocal idx
        key = f"__{tag}_{idx}__"
        mapping[key] = m.group(0)
        idx += 1
        return key

    # Thứ tự: code block -> inline code -> URL
    text = _CODEBLOCK_RE.sub(lambda m: repl_cb(m, "CODEBLOCK"), text)
    text = _INLINECODE_RE.sub(lambda m: repl_cb(m, "INLINECODE"), text)
    text = _URL_RE.sub(lambda m: repl_cb(m, "URL"), text)
    return text, mapping

def _restore_markdown(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text

# ---------- Block split/metrics ----------
def _split_blocks(text: str):
    """
    Chia theo đoạn, vẫn giữ dòng trống. Trả về list các block (bao gồm block = '\n' cho khoảng trắng).
    """
    # chuẩn hoá \r\n -> \n
    t = text.replace("\r\n", "\n")
    parts = re.split(r"(\n{2,})", t)  # tách và giữ delimiter (dòng trống)
    blocks = []
    for p in parts:
        if not p:
            continue
        if p.startswith("\n"):
            # giữ nguyên các dòng trống như một block riêng
            blocks.append(p)
        else:
            blocks.append(p)
    return blocks

def _count_lines(s: str) -> int:
    return s.replace("\r\n", "\n").count("\n") + 1 if s.strip() else 0

def _looks_collapsed(src: str, out: str) -> bool:
    """
    Heuristic: đầu vào có nhiều dòng, đầu ra quá ngắn hoặc chỉ 1 dòng -> có thể bị gộp.
    """
    src_lines = _count_lines(src)
    out_lines = _count_lines(out)
    if src_lines >= 2 and out_lines <= 1:
        # thêm điều kiện độ dài để tránh false-positive khi đoạn rất ngắn
        return len(out.strip()) < max(200, int(len(src.strip()) * 0.7))
    return False

# ========== Primary: Gemini ==========
def call_gemini_translate(text: str, target_language: str = "vi") -> str:
    if not API_KEY or not GEMINI_URL:
        return "[Lỗi dịch]"
    tgt_code = _norm_lang(target_language)
    tgt_name = _LANG_NAME.get(tgt_code, "Vietnamese")

    prompt_text = f"""You are a translation engine.
Translate the following text into {tgt_name}.

STRICT RULES:
- Preserve the original Markdown structure and line breaks EXACTLY (headings, lists, quotes, bold/italic, tables, code blocks).
- Do NOT translate anything inside triple backticks ```...``` or inline backticks `...`.
- Do NOT alter or translate URLs.
- Do NOT add explanations, notes, or extra lines.
- Return ONLY the translated Markdown content, nothing else.

---BEGIN SOURCE---
{text}
---END SOURCE---"""

    headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt_text}]}]}
    try:
        resp = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return "🔁 " + out
    except Exception:
        return "[Lỗi dịch]"

# ========== Secondary: googletrans ==========
def _call_googletrans(text: str, target_language: str) -> str:
    if not _HAVE_GOOGLETRANS:
        raise RuntimeError("googletrans not installed")
    protected, mapping = _protect_markdown(text)
    dest = _norm_lang(target_language)
    result = _GT.translate(protected, dest=dest)
    out = (result.text or "").strip()
    if not out:
        raise RuntimeError("googletrans returned empty")
    return _restore_markdown(out, mapping)

# ========== Tertiary: LibreTranslate ==========
def _call_libretranslate(text: str, target_language: str) -> str:
    if not FREE_TRANSLATE_URL:
        raise RuntimeError("FREE_TRANSLATE_URL is not set")
    protected, mapping = _protect_markdown(text)
    tgt = _norm_lang(target_language)
    payload = {"q": protected, "source": "auto", "target": tgt, "format": "text"}
    if FREE_TRANSLATE_API_KEY:
        payload["api_key"] = FREE_TRANSLATE_API_KEY
    r = requests.post(FREE_TRANSLATE_URL, json=payload, timeout=FREE_TRANSLATE_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    out = (data.get("translatedText") or data.get("translation") or "").strip()
    if not out:
        raise RuntimeError("LibreTranslate returned empty")
    return _restore_markdown(out, mapping)

# ---------- Blockwise translation if collapsed ----------
def _blockwise_translate(engine_fn, text: str, target_language: str) -> str:
    """
    Dịch từng block (đoạn/dòng) rồi ghép lại.
    engine_fn: callable(text, target_language) -> str
    """
    blocks = _split_blocks(text)
    outputs = []
    for b in blocks:
        # Nếu là block toàn khoảng trắng (dòng trống), giữ nguyên
        if not b.strip():
            outputs.append(b)
            continue
        try:
            out = engine_fn(b, target_language)
        except Exception:
            out = ""
        outputs.append(out if out is not None else "")
    return "".join(outputs).strip()

# ========== Public API: dịch với fallback ==========
def translate_with_fallback(text: str, target_language: str = "vi") -> str:
    """
    Chuỗi fallback:
        1) Gemini (prefix 🔁)
        2) googletrans (prefix 🌐)
        3) LibreTranslate (prefix 🆓)
    Có cơ chế phát hiện bản dịch bị "rút gọn 1 dòng" -> dịch lại theo block để không rớt câu.
    """
    text = text or ""
    if not text.strip():
        return ""

    # 1) Gemini
    try:
        g = call_gemini_translate(text, target_language=target_language)
        if g and not g.strip().lower().startswith(("[lỗi dịch]", "[loi dich]")):
            g_body = g[2:].strip() if g.startswith("🔁 ") else g
            if _looks_collapsed(text, g_body):
                # Dịch lại theo block để không mất dòng
                g2 = _blockwise_translate(lambda t, lang: call_gemini_translate(t, lang)[2:], text, target_language)
                if g2:
                    return "🔁 " + g2
            return g
    except Exception:
        pass

    # 2) googletrans
    try:
        gt = _call_googletrans(text, target_language)
        if gt:
            if _looks_collapsed(text, gt):
                gt = _blockwise_translate(_call_googletrans, text, target_language)
            return "🌐 " + gt
    except Exception:
        pass

    # 3) LibreTranslate
    try:
        lt = _call_libretranslate(text, target_language)
        if lt:
            if _looks_collapsed(text, lt):
                lt = _blockwise_translate(_call_libretranslate, text, target_language)
            return "🆓 " + lt
    except Exception:
        pass

    # 4) Hết cách
    return ""
