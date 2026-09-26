"""
nlu.py — NLU using free, locally-run Hugging Face models, with keyword fallback.
"""

from functools import lru_cache

INTENT_LABELS = [
    "potential fishing zone",
    "sea safety advisory",
    "weather and tide conditions",
    "cyclone or lightning alert",
    "chlorophyll and sea surface temperature analysis",
    "route optimization for a vessel",
    "explain decline in fish productivity",
    "geofencing or restricted zone check",
]

NLLB_CODES = {
    "en": "eng_Latn", "hi": "hin_Deva", "ta": "tam_Taml", "te": "tel_Telu",
    "kn": "kan_Knda", "ml": "mal_Mlym", "bn": "ben_Beng", "mr": "mar_Deva",
    "gu": "guj_Gujr", "pa": "pan_Guru", "ur": "urd_Arab", "or": "ory_Orya",
}

_HF_AVAILABLE = True
try:
    from transformers import pipeline
except Exception:
    _HF_AVAILABLE = False


@lru_cache(maxsize=1)
def _zero_shot():
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")


@lru_cache(maxsize=1)
def _lang_detect():
    return pipeline("text-classification", model="papluca/xlm-roberta-base-language-detection")


@lru_cache(maxsize=1)
def _translator():
    return pipeline("translation", model="facebook/nllb-200-distilled-600M")


@lru_cache(maxsize=1)
def _generator():
    return pipeline("text2text-generation", model="google/flan-t5-base")


_KEYWORD_MAP = {
    "potential fishing zone": ["pfz", "fishing zone", "where to fish", "nearest fishing"],
    "sea safety advisory": ["safe to venture", "is it safe", "should i go", "safe to sail"],
    "weather and tide conditions": ["tide", "weather", "wind", "wave", "sea condition"],
    "cyclone or lightning alert": ["cyclone", "lightning", "storm", "alert", "warning"],
    "chlorophyll and sea surface temperature analysis": ["chlorophyll", "sst", "sea surface temperature"],
    "route optimization for a vessel": ["route", "navigate", "path", "course to"],
    "explain decline in fish productivity": ["decline", "productivity", "why has fish", "less fish"],
    "geofencing or restricted zone check": ["geofence", "boundary", "restricted", "protected area", "imbl"],
}


def detect_language(text: str) -> str:
    if _HF_AVAILABLE:
        try:
            res = _lang_detect()(text[:512])[0]
            return res["label"]
        except Exception:
            pass
    return "en"


def translate(text: str, src: str, tgt: str) -> str:
    if src == tgt or src not in NLLB_CODES or tgt not in NLLB_CODES:
        return text
    if _HF_AVAILABLE:
        try:
            out = _translator()(text, src_lang=NLLB_CODES[src], tgt_lang=NLLB_CODES[tgt])
            return out[0]["translation_text"]
        except Exception:
            pass
    return text


def classify_intent(text: str) -> dict:
    if _HF_AVAILABLE:
        try:
            res = _zero_shot()(text, INTENT_LABELS, multi_label=False)
            return {"intent": res["labels"][0], "confidence": round(res["scores"][0], 3),
                    "method": "hf-zero-shot"}
        except Exception:
            pass
    low = text.lower()
    for intent, kws in _KEYWORD_MAP.items():
        if any(kw in low for kw in kws):
            return {"intent": intent, "confidence": 0.6, "method": "keyword-fallback"}
    return {"intent": "sea safety advisory", "confidence": 0.3, "method": "default-fallback"}


def phrase_response(prompt: str) -> str:
    if _HF_AVAILABLE:
        try:
            out = _generator()(prompt, max_new_tokens=200)
            return out[0]["generated_text"]
        except Exception:
            pass
    return None
