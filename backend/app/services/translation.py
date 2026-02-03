"""
Translation Service - "Translation Sandwich" Implementation
Enables multi-language support for medical tourism leads.

Flow:
1. Detect incoming language
2. Translate user input → English (for LLM reasoning)
3. Process with LLM (medical accuracy in English)
4. Translate response → User's language
"""

import os
import deepl
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()

# DeepL API Configuration
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")

# Supported languages (ISO 639-1 codes)
SUPPORTED_LANGUAGES = {
    "EN": "English",
    "DE": "German",
    "FR": "French",
    "ES": "Spanish",
    "IT": "Italian",
    "PT": "Portuguese",
    "NL": "Dutch",
    "PL": "Polish",
    "RU": "Russian",
    "JA": "Japanese",
    "ZH": "Chinese",
    "AR": "Arabic",
    "TR": "Turkish",
}


class TranslationService:
    """
    Handles the "Translation Sandwich" pattern:
    Input (any language) → English → LLM → English → Output (original language)
    """

    def __init__(self):
        self.translator = None
        if DEEPL_API_KEY:
            try:
                self.translator = deepl.Translator(DEEPL_API_KEY)
            except Exception as e:
                print(f"DeepL initialization error: {e}")

    def detect_language(self, text: str) -> str:
        """
        Detect the language of input text.
        Returns ISO 639-1 language code (e.g., 'DE' for German).
        """
        if not self.translator or not text.strip():
            return "EN"

        try:
            # DeepL doesn't have a dedicated detect endpoint,
            # but we can use a minimal translation to detect
            result = self.translator.translate_text(
                text[:100],  # Use first 100 chars for speed
                target_lang="EN-US",
            )
            detected = result.detected_source_lang
            return detected if detected in SUPPORTED_LANGUAGES else "EN"
        except Exception as e:
            print(f"Language detection error: {e}")
            return "EN"

    def translate_to_english(
        self, text: str, source_lang: str = None
    ) -> Tuple[str, str]:
        """
        Translate input text to English for LLM processing.

        Returns:
            Tuple of (translated_text, detected_language)
        """
        if not self.translator:
            return text, "EN"

        try:
            # Detect language if not provided
            if not source_lang:
                source_lang = self.detect_language(text)

            # If already English, return as-is
            if source_lang.startswith("EN"):
                return text, "EN"

            # Translate to English
            result = self.translator.translate_text(
                text, source_lang=source_lang, target_lang="EN-US"
            )

            return result.text, source_lang

        except Exception as e:
            print(f"Translation to English error: {e}")
            return text, "EN"

    def translate_from_english(self, text: str, target_lang: str) -> str:
        """
        Translate LLM response from English to target language.
        """
        if not self.translator:
            return text

        # If target is English, return as-is
        if target_lang.startswith("EN"):
            return text

        try:
            result = self.translator.translate_text(
                text, source_lang="EN", target_lang=target_lang
            )
            return result.text

        except Exception as e:
            print(f"Translation from English error: {e}")
            return text

    def translate_sandwich(
        self, user_input: str, llm_processor: callable, source_lang: str = None
    ) -> Tuple[str, str]:
        """
        Complete "Translation Sandwich" flow:
        1. Translate input to English
        2. Process with LLM
        3. Translate response back

        Args:
            user_input: User's message in any language
            llm_processor: Function that takes English text and returns response
            source_lang: Optional pre-detected language

        Returns:
            Tuple of (translated_response, detected_language)
        """
        # Step 1: Translate input to English
        english_input, detected_lang = self.translate_to_english(
            user_input, source_lang
        )

        # Step 2: Process with LLM (in English for accuracy)
        english_response = llm_processor(english_input)

        # Step 3: Translate response back to user's language
        final_response = self.translate_from_english(english_response, detected_lang)

        return final_response, detected_lang

    def get_language_name(self, lang_code: str) -> str:
        """Get human-readable language name from code."""
        return SUPPORTED_LANGUAGES.get(lang_code, "English")

    @property
    def is_available(self) -> bool:
        """Check if translation service is properly configured."""
        return self.translator is not None


# Singleton instance
translation_service = TranslationService()
