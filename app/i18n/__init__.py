from app.i18n.en import LABELS as EN_LABELS
from app.i18n.th import LABELS as TH_LABELS

SUPPORTED_LANGS = {"th", "en"}


def get_labels(lang: str):
    if lang == "en":
        return EN_LABELS
    return TH_LABELS


def normalize_lang(lang: str | None, default: str = "th") -> str:
    if lang in SUPPORTED_LANGS:
        return lang
    if default in SUPPORTED_LANGS:
        return default
    return "th"


__all__ = ["EN_LABELS", "SUPPORTED_LANGS", "TH_LABELS", "get_labels", "normalize_lang"]
