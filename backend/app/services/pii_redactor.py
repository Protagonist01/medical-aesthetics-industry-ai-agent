"""
PII Redaction Service
PRD v1.2: HIPAA-Compliant Data Sanitization

Provides regex-based PII detection and redaction before LLM processing.
Masks sensitive data while preserving conversation context.
"""

import re
from typing import Dict, List, Tuple


class PIIRedactor:
    """
    PII Redaction Service for HIPAA compliance.
    Detects and masks personally identifiable information.
    """

    def __init__(self):
        # Compile regex patterns for performance
        self.patterns: List[Tuple[str, re.Pattern, str]] = [
            # SSN patterns
            (
                "SSN",
                re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
                "[SSN REDACTED]",
            ),
            # Credit card patterns (major brands)
            (
                "CREDIT_CARD",
                re.compile(
                    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9][0-9])[0-9]{12})\b"
                ),
                "[CARD REDACTED]",
            ),
            # US Passport
            (
                "PASSPORT",
                re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
                "[PASSPORT REDACTED]",
            ),
            # Date of birth patterns
            (
                "DOB",
                re.compile(
                    r"\b(?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])[/\-.](?:19|20)\d{2}\b"
                ),
                "[DOB REDACTED]",
            ),
            # Email (partial mask - keep domain visible)
            (
                "EMAIL",
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
                None,  # Special handling
            ),
            # Phone numbers (various formats)
            (
                "PHONE",
                re.compile(
                    r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"
                ),
                None,  # Special handling
            ),
            # Medical record numbers (common formats)
            (
                "MRN",
                re.compile(r"\bMRN[:\s#]*\d{6,12}\b", re.IGNORECASE),
                "[MRN REDACTED]",
            ),
            # Insurance ID patterns
            (
                "INSURANCE_ID",
                re.compile(r"\b[A-Z]{3}\d{9,11}\b"),
                "[INSURANCE_ID REDACTED]",
            ),
            # Driver's license (common formats)
            (
                "DL",
                re.compile(r"\b[A-Z]{1,2}\d{5,8}\b"),
                "[DL REDACTED]",
            ),
        ]

    def redact(self, text: str, preserve_context: bool = True) -> Dict:
        """
        Redact PII from text.

        Args:
            text: Input text to redact
            preserve_context: If True, use partial masking for some fields

        Returns:
            Dict with 'redacted_text' and 'detections' list
        """
        redacted = text
        detections: List[Dict] = []

        for pii_type, pattern, replacement in self.patterns:
            matches = pattern.findall(redacted)

            for match in matches:
                if pii_type == "EMAIL" and preserve_context:
                    # Partial mask: j***@example.com
                    parts = match.split("@")
                    if len(parts) == 2:
                        masked = f"{parts[0][0]}***@{parts[1]}"
                        redacted = redacted.replace(match, masked)
                        detections.append(
                            {
                                "type": pii_type,
                                "original": match,
                                "masked": masked,
                            }
                        )
                elif pii_type == "PHONE" and preserve_context:
                    # Partial mask: ***-***-1234
                    digits = re.sub(r"\D", "", match)
                    if len(digits) >= 4:
                        masked = f"***-***-{digits[-4:]}"
                        redacted = redacted.replace(match, masked)
                        detections.append(
                            {
                                "type": pii_type,
                                "original": match,
                                "masked": masked,
                            }
                        )
                elif replacement:
                    redacted = redacted.replace(match, replacement)
                    detections.append(
                        {
                            "type": pii_type,
                            "original": match,
                            "masked": replacement,
                        }
                    )

        return {
            "redacted_text": redacted,
            "detections": detections,
            "pii_detected": len(detections) > 0,
        }

    def mask_for_logging(self, text: str) -> str:
        """
        Aggressive redaction for logging purposes.
        Completely removes all detected PII.
        """
        result = self.redact(text, preserve_context=False)
        return result["redacted_text"]

    def get_pii_summary(self, text: str) -> Dict:
        """
        Get summary of PII types found without modifying text.
        Useful for compliance auditing.
        """
        result = self.redact(text)
        pii_types = {}

        for detection in result["detections"]:
            pii_type = detection["type"]
            pii_types[pii_type] = pii_types.get(pii_type, 0) + 1

        return {
            "total_pii_found": len(result["detections"]),
            "pii_types": pii_types,
            "has_sensitive_data": len(result["detections"]) > 0,
        }


# Singleton instance
pii_redactor = PIIRedactor()


def redact_pii(text: str) -> str:
    """Convenience function to redact PII from text"""
    return pii_redactor.redact(text)["redacted_text"]


def check_pii(text: str) -> bool:
    """Check if text contains PII"""
    return pii_redactor.get_pii_summary(text)["has_sensitive_data"]
