r"""
Presidio-Based PII Recognition and Anonymization Engine
Business Case ID: BC-AAIE-HACK-06 (Section 6: Security & Governance)

Features:
- Uses presidio-analyzer and presidio-anonymizer for industry-standard PII detection.
- Custom PatternRecognizers for insurance identifiers:
    - Policy Numbers: POL-\d{4,10}-[A-Z]{2}
    - Claimant IDs: CLM-\d{4,10}-[A-Z]{2}
- Automatically masks names, emails, phone numbers, SSNs, credit cards, and addresses.
- Preserves policy clause IDs intact (e.g., POL-SEC-04-COLLISION, CL-COLL-04).
- Safe deterministic fallback if Presidio is unavailable or in offline environments.
"""

import re
from typing import Tuple, List, Dict, Any, Optional

try:
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    HAS_PRESIDIO = True
except ImportError:
    HAS_PRESIDIO = False


_ANALYZER = None
_ANONYMIZER = None


def _get_presidio_engines():
    global _ANALYZER, _ANONYMIZER
    if not HAS_PRESIDIO:
        return None, None
    if _ANALYZER is None:
        try:
            _ANALYZER = AnalyzerEngine()
            # Custom Recognizer for Policy Numbers
            pol_pattern = Pattern(name="policy_number_pattern", regex=r"\bPOL-\d{4,10}-[A-Z]{2}\b", score=0.95)
            pol_recognizer = PatternRecognizer(
                supported_entity="POLICY_NUMBER",
                patterns=[pol_pattern],
                context=["policy", "insurance", "pol"]
            )
            _ANALYZER.registry.add_recognizer(pol_recognizer)

            # Custom Recognizer for Claimant IDs
            clm_pattern = Pattern(name="claimant_id_pattern", regex=r"\bCLM-\d{4,10}-[A-Z]{2}\b", score=0.95)
            clm_recognizer = PatternRecognizer(
                supported_entity="CLAIMANT_ID",
                patterns=[clm_pattern],
                context=["claimant", "claim", "clm"]
            )
            _ANALYZER.registry.add_recognizer(clm_recognizer)

            _ANONYMIZER = AnonymizerEngine()
        except Exception:
            _ANALYZER = None
            _ANONYMIZER = None
    return _ANALYZER, _ANONYMIZER


def sanitize_text_with_presidio(text: str) -> Tuple[str, int, List[str]]:
    """Sanitize and anonymize sensitive PII using Presidio with custom insurance recognizers.
    
    Returns:
        (sanitized_text, redacted_pii_count, detected_entity_types)
    """
    if not text:
        return "", 0, []

    analyzer, anonymizer = _get_presidio_engines()
    if analyzer and anonymizer:
        try:
            results = analyzer.analyze(text=text, language="en")
            # Filter out false positives on policy clauses (e.g. POL-SEC-04-COLLISION)
            valid_results = []
            for r in results:
                entity_slice = text[r.start:r.end]
                if "SEC-" in entity_slice or "EXCL-" in entity_slice or entity_slice.startswith("CL-"):
                    continue
                valid_results.append(r)

            if valid_results:
                def mask_pol(val: str) -> str:
                    parts = val.split("-")
                    return f"POL-***-{parts[-1]}" if len(parts) >= 2 else "POL-***-US"

                def mask_clm(val: str) -> str:
                    parts = val.split("-")
                    return f"CLM-***-{parts[-1]}" if len(parts) >= 2 else "CLM-***-US"

                anonymized = anonymizer.anonymize(
                    text=text,
                    analyzer_results=valid_results,
                    operators={
                        "POLICY_NUMBER": OperatorConfig("custom", {"lambda": mask_pol}),
                        "CLAIMANT_ID": OperatorConfig("custom", {"lambda": mask_clm}),
                        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE_REDACTED]"}),
                        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL_REDACTED]"}),
                        "PERSON": OperatorConfig("replace", {"new_value": "[NAME_REDACTED]"}),
                        "DEFAULT": OperatorConfig("replace", {"new_value": "[PII_REDACTED]"})
                    }
                )
                detected = sorted(list(set(r.entity_type for r in valid_results)))
                return anonymized.text, len(valid_results), detected
        except Exception as e:
            pass

    # Regex Fallback
    redacted_count = 0
    detected_types = []
    sanitized = text

    # Strict Policy pattern
    pol_matches = re.findall(r"\bPOL-\d{4,10}-[A-Z]{2}\b", sanitized)
    if pol_matches:
        redacted_count += len(pol_matches)
        detected_types.append("POLICY_NUMBER")
        sanitized = re.sub(
            r"\bPOL-\d{4,10}-[A-Z]{2}\b",
            lambda m: f"POL-***-{m.group(0).split('-')[-1]}",
            sanitized
        )

    # Strict Claimant pattern
    clm_matches = re.findall(r"\bCLM-\d{4,10}-[A-Z]{2}\b", sanitized)
    if clm_matches:
        redacted_count += len(clm_matches)
        detected_types.append("CLAIMANT_ID")
        sanitized = re.sub(
            r"\bCLM-\d{4,10}-[A-Z]{2}\b",
            lambda m: f"CLM-***-{m.group(0).split('-')[-1]}",
            sanitized
        )

    # SSN pattern
    ssn_matches = re.findall(r"\b\d{3}-\d{2}-\d{4}\b", sanitized)
    if ssn_matches:
        redacted_count += len(ssn_matches)
        detected_types.append("US_SSN")
        sanitized = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", sanitized)

    # Email pattern
    email_matches = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", sanitized)
    if email_matches:
        redacted_count += len(email_matches)
        detected_types.append("EMAIL_ADDRESS")
        sanitized = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]", sanitized)

    # Phone pattern
    phone_matches = re.findall(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b", sanitized)
    if phone_matches:
        redacted_count += len(phone_matches)
        detected_types.append("PHONE_NUMBER")
        sanitized = re.sub(r"\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b", "[PHONE_REDACTED]", sanitized)

    return sanitized, redacted_count, detected_types
