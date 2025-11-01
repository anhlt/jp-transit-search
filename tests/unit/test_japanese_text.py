"""Tests for Japanese text processing utilities."""

import threading

import pytest

from jp_transit_search.utils.japanese_text import JapaneseTextConverter, get_converter


class TestJapaneseTextConverter:
    """Test cases for JapaneseTextConverter class."""

    def test_init(self):
        """Test converter initialization."""
        converter = JapaneseTextConverter()
        assert converter._kks is not None

    def test_to_hiragana_basic(self):
        """Test basic kanji to hiragana conversion."""
        converter = JapaneseTextConverter()

        # Basic kanji conversion
        assert converter.to_hiragana("新宿") == "しんじゅく"
        assert converter.to_hiragana("東京") == "とうきょう"
        assert converter.to_hiragana("渋谷") == "しぶや"

    def test_to_hiragana_katakana_input(self):
        """Test katakana to hiragana conversion."""
        converter = JapaneseTextConverter()

        # Katakana should convert to hiragana
        assert converter.to_hiragana("シンジュク") == "しんじゅく"
        assert converter.to_hiragana("トウキョウ") == "とうきょう"

    def test_to_hiragana_mixed_input(self):
        """Test mixed text to hiragana conversion."""
        converter = JapaneseTextConverter()

        # Mixed kanji and kana
        assert converter.to_hiragana("新宿駅") == "しんじゅくえき"
        assert converter.to_hiragana("東京メトロ") == "とうきょうめとろ"

    def test_to_katakana_basic(self):
        """Test basic kanji to katakana conversion."""
        converter = JapaneseTextConverter()

        # Basic kanji conversion
        assert converter.to_katakana("新宿") == "シンジュク"
        assert converter.to_katakana("東京") == "トウキョウ"
        assert converter.to_katakana("渋谷") == "シブヤ"

    def test_to_katakana_hiragana_input(self):
        """Test hiragana to katakana conversion."""
        converter = JapaneseTextConverter()

        # Hiragana should convert to katakana
        assert converter.to_katakana("しんじゅく") == "シンジュク"
        assert converter.to_katakana("とうきょう") == "トウキョウ"

    def test_to_romaji_basic(self):
        """Test basic kanji to romaji conversion."""
        converter = JapaneseTextConverter()

        # Basic kanji conversion
        result = converter.to_romaji("新宿")
        assert result == "shinjuku"

        result = converter.to_romaji("東京")
        assert result == "toukyou"

        result = converter.to_romaji("渋谷")
        assert result == "shibuya"

    def test_to_romaji_kana_input(self):
        """Test kana to romaji conversion."""
        converter = JapaneseTextConverter()

        # Hiragana input
        assert converter.to_romaji("しんじゅく") == "shinjuku"
        assert converter.to_romaji("とうきょう") == "toukyou"

        # Katakana input
        assert converter.to_romaji("シンジュク") == "shinjuku"
        assert converter.to_romaji("トウキョウ") == "toukyou"

    def test_normalize_for_search_basic(self):
        """Test basic text normalization."""
        converter = JapaneseTextConverter()

        # Should remove station suffixes
        assert converter.normalize_for_search("新宿駅") == "新宿"
        assert converter.normalize_for_search("渋谷駅") == "渋谷"

        # Should handle text without suffixes
        assert converter.normalize_for_search("新宿") == "新宿"

    def test_normalize_for_search_whitespace(self):
        """Test whitespace and special character normalization."""
        converter = JapaneseTextConverter()

        # Should remove spaces and special characters
        assert converter.normalize_for_search("新宿 駅") == "新宿"
        assert converter.normalize_for_search("新宿-駅") == "新宿"
        assert converter.normalize_for_search("新宿ー駅") == "新宿"

    def test_normalize_for_search_particles(self):
        """Test particle removal normalization."""
        converter = JapaneseTextConverter()

        # Should remove particles
        assert converter.normalize_for_search("新宿の駅") == "新宿"
        assert converter.normalize_for_search("新宿ノ駅") == "新宿"

    def test_generate_all_variants_basic(self):
        """Test generating all text variants."""
        converter = JapaneseTextConverter()

        variants = converter.generate_all_variants("新宿")

        assert "original" in variants
        assert "hiragana" in variants
        assert "katakana" in variants
        assert "romaji" in variants
        assert "normalized" in variants

        assert variants["original"] == "新宿"
        assert variants["hiragana"] == "しんじゅく"
        assert variants["katakana"] == "シンジュク"
        assert variants["romaji"] == "shinjuku"

    def test_generate_all_variants_empty_input(self):
        """Test generating variants for empty input."""
        converter = JapaneseTextConverter()

        variants = converter.generate_all_variants("")

        # Should handle empty input gracefully
        assert variants["original"] == ""
        assert variants["hiragana"] == ""
        assert variants["katakana"] == ""
        assert variants["romaji"] == ""

    def test_generate_all_variants_english_input(self):
        """Test generating variants for English input."""
        converter = JapaneseTextConverter()

        variants = converter.generate_all_variants("Tokyo Station")

        assert variants["original"] == "Tokyo Station"
        # English text should remain mostly unchanged for hiragana/katakana
        # but should be normalized (removing spaces/special chars)
        assert variants["normalized"] == "TokyoStation"
        # Romaji conversion of English should be lowercase
        assert "tokyo" in variants["romaji"].lower()

    def test_generate_all_variants_mixed_input(self):
        """Test generating variants for mixed Japanese-English input."""
        converter = JapaneseTextConverter()

        variants = converter.generate_all_variants("新宿Station")

        assert variants["original"] == "新宿Station"
        # Should handle mixed content appropriately
        assert "しんじゅく" in variants["hiragana"]
        assert "シンジュク" in variants["katakana"]

    def test_error_handling_none_input(self):
        """Test error handling for None input."""
        converter = JapaneseTextConverter()

        # Should handle None input gracefully
        with pytest.raises((TypeError, AttributeError)):
            converter.to_hiragana(None)

    def test_long_text_processing(self):
        """Test processing of longer text strings."""
        converter = JapaneseTextConverter()

        long_text = "東京都新宿区西新宿二丁目八番一号"

        hiragana = converter.to_hiragana(long_text)
        katakana = converter.to_katakana(long_text)
        romaji = converter.to_romaji(long_text)

        # Should handle long text without errors
        assert len(hiragana) > 0
        assert len(katakana) > 0
        assert len(romaji) > 0

        # All should be different representations
        assert hiragana != katakana
        assert hiragana != romaji
        assert katakana != romaji

    def test_station_name_conversions(self):
        """Test conversions for common station names."""
        converter = JapaneseTextConverter()

        station_names = [
            "新宿",
            "渋谷",
            "池袋",
            "上野",
            "品川",
            "東京",
            "横浜",
            "大阪",
            "京都",
            "神戸",
        ]

        for station in station_names:
            variants = converter.generate_all_variants(station)

            # Each station should have all variants
            assert len(variants["hiragana"]) > 0
            assert len(variants["katakana"]) > 0
            assert len(variants["romaji"]) > 0

            # Hiragana should be different from katakana
            assert variants["hiragana"] != variants["katakana"]

    def test_consistency_across_methods(self):
        """Test that individual methods are consistent with generate_variants."""
        converter = JapaneseTextConverter()

        test_text = "新宿"

        # Individual method calls
        _hiragana = converter.to_hiragana(test_text)
        _katakana = converter.to_katakana(test_text)
        normalized = converter.normalize_for_search(test_text)

        # generate_all_variants call
        variants = converter.generate_all_variants(test_text)

        # Should be consistent (note: variants uses normalized text as input)
        assert converter.to_hiragana(normalized) == variants["hiragana"]
        assert converter.to_katakana(normalized) == variants["katakana"]
        assert converter.to_romaji(normalized) == variants["romaji"]
        assert normalized == variants["normalized"]


class TestGetConverter:
    """Test cases for the get_converter singleton function."""

    def test_get_converter_returns_instance(self):
        """Test that get_converter returns a valid instance."""
        converter = get_converter()
        assert isinstance(converter, JapaneseTextConverter)
        assert converter._kks is not None

    def test_get_converter_returns_same_instance(self):
        """Test that get_converter returns the same instance on multiple calls."""
        converter1 = get_converter()
        converter2 = get_converter()
        assert converter1 is converter2

    def test_get_converter_thread_safety(self):
        """Test that get_converter is thread-safe."""
        # Reset the global converter to test initialization
        import jp_transit_search.utils.japanese_text as jt_module

        original_converter = jt_module._converter
        jt_module._converter = None

        try:
            instances = []
            barrier = threading.Barrier(10)

            def get_instance():
                # Synchronize all threads to start at the same time
                barrier.wait()
                instance = get_converter()
                instances.append(instance)

            # Create multiple threads that all try to get the converter at once
            threads = [threading.Thread(target=get_instance) for _ in range(10)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # All threads should get the same instance
            assert len(instances) == 10
            assert all(instance is instances[0] for instance in instances)
        finally:
            # Restore the original converter
            jt_module._converter = original_converter

