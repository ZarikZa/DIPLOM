import re


class ProfanityValidator:
    TOKEN_RE = re.compile(r"[A-Za-z\u0400-\u04FF0-9]+", flags=re.UNICODE)
    LEET_MAP = str.maketrans(
        {
            "@": "a",
            "$": "s",
            "0": "o",
            "1": "i",
            "3": "e",
            "4": "a",
            "5": "s",
            "6": "b",
            "7": "t",
            "8": "b",
            "9": "g",
        }
    )
    BLOCKED_STEMS = (
        "бля",
        "бляд",
        "пизд",
        "хуй",
        "хуе",
        "еба",
        "ебл",
        "ебн",
        "ебуч",
        "пидор",
        "пидар",
        "долбоеб",
        "долбаеб",
        "мудил",
        "гандон",
        "залуп",
        "suka",
        "blya",
        "xuy",
        "huy",
        "pizd",
        "eban",
        "fuck",
        "shit",
        "bitch",
        "cunt",
        "asshole",
        "motherf",
    )

    @classmethod
    def _normalize_token(cls, token: str) -> str:
        normalized = token.lower().replace("ё", "е")
        normalized = normalized.translate(cls.LEET_MAP)
        normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
        return normalized

    @classmethod
    def contains_profanity(cls, value: str | None) -> bool:
        if value is None:
            return False

        for raw_token in cls.TOKEN_RE.findall(str(value)):
            token = cls._normalize_token(raw_token)
            for stem in cls.BLOCKED_STEMS:
                if stem in token:
                    return True
        return False

    @classmethod
    def ensure_clean(cls, value: str, field_label: str) -> str:
        text = (value or "").strip()
        if not text:
            return text
        if cls.contains_profanity(text):
            raise ValueError(f"{field_label} содержит нецензурную лексику.")
        return text
