"""Japanese text processing utilities."""

import re
import threading
from typing import Any

import jaconv
import pykakasi


class JapaneseTextConverter:
    """Handles conversion between Japanese text formats."""

    def __init__(self) -> None:
        """Initialize the converter with lazy pykakasi initialization."""
        self._kks: Any = None
        self._lock = threading.Lock()

    def _get_kakasi(self) -> Any:
        """Get pykakasi converter with thread-safe lazy initialization."""
        if self._kks is None:
            with self._lock:
                if self._kks is None:  # Double-check locking pattern
                    self._kks = pykakasi.kakasi()
        return self._kks

    def to_hiragana(self, text: str) -> str:
        """Convert text to hiragana."""
        # First convert katakana to hiragana
        hiragana = jaconv.kata2hira(text)

        # Then convert kanji to hiragana using pykakasi
        result = self._get_kakasi().convert(hiragana)
        return "".join([item["hira"] for item in result])

    def to_katakana(self, text: str) -> str:
        """Convert text to katakana."""
        # First convert to hiragana, then to katakana
        hiragana = self.to_hiragana(text)
        return jaconv.hira2kata(hiragana)

    def to_romaji(self, text: str) -> str:
        """Convert text to romaji."""
        result = self._get_kakasi().convert(text)
        return "".join([item["hepburn"] for item in result])

    def normalize_for_search(self, text: str) -> str:
        """Normalize text for fuzzy search by removing common suffixes and particles."""
        # Remove common station suffixes
        text = re.sub(r"[駅站]$", "", text)

        # Remove common particles and suffixes that might interfere with search
        text = re.sub(r"[のノ]", "", text)

        # Normalize spaces and special characters
        text = re.sub(r"[\s\-ー−・]", "", text)

        return text.strip()

    def generate_all_variants(self, text: str) -> dict[str, str]:
        """Generate all text variants for a station name."""
        normalized = self.normalize_for_search(text)

        variants = {
            "original": text,
            "normalized": normalized,
            "hiragana": self.to_hiragana(normalized),
            "katakana": self.to_katakana(normalized),
            "romaji": self.to_romaji(normalized),
        }

        return variants


# Thread-safe singleton implementation
_converter: JapaneseTextConverter | None = None
_converter_lock = threading.Lock()


def get_converter() -> JapaneseTextConverter:
    """Get a thread-safe singleton instance of the Japanese text converter."""
    global _converter
    if _converter is None:
        with _converter_lock:
            if _converter is None:  # Double-check locking pattern
                _converter = JapaneseTextConverter()
    return _converter


def convert_to_hiragana(text: str) -> str:
    """Convert text to hiragana."""
    return get_converter().to_hiragana(text)


def convert_to_katakana(text: str) -> str:
    """Convert text to katakana."""
    return get_converter().to_katakana(text)


def convert_to_romaji(text: str) -> str:
    """Convert text to romaji."""
    return get_converter().to_romaji(text)


def generate_text_variants(text: str) -> dict[str, str]:
    """Generate all text variants for a station name."""
    return get_converter().generate_all_variants(text)


def is_likely_romaji(text: str) -> bool:
    """Check if text is likely romaji (Latin characters).
    
    Args:
        text: Input text to check
        
    Returns:
        True if text appears to be romaji, False otherwise
    """
    if not text:
        return False
    
    # Remove spaces, punctuation, and numbers for analysis
    clean_text = re.sub(r'[\s\d\-\.,;:!?()[\]{}"\'/\\]+', '', text)
    
    if not clean_text:
        return False
    
    # Count Latin characters (a-z, A-Z)
    latin_chars = len(re.findall(r'[a-zA-Z]', clean_text))
    
    # Count Japanese characters (hiragana, katakana, kanji)
    hiragana_chars = len(re.findall(r'[\u3040-\u309f]', clean_text))
    katakana_chars = len(re.findall(r'[\u30a0-\u30ff]', clean_text))
    kanji_chars = len(re.findall(r'[\u4e00-\u9faf]', clean_text))
    
    japanese_chars = hiragana_chars + katakana_chars + kanji_chars
    total_chars = len(clean_text)
    
    # If more than 70% of characters are Latin, likely romaji
    if total_chars > 0 and latin_chars / total_chars > 0.7:
        return True
    
    # If there are Latin characters but no Japanese characters, likely romaji
    if latin_chars > 0 and japanese_chars == 0:
        return True
    
    return False
