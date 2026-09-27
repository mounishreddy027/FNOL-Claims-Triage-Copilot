"""
Context Engineering - Summarization & Compression Middleware
Business Case ID: BC-AAIE-HACK-06

Compresses unstructured, verbose claim narratives into concise, standardized loss facts.
Selects salient attributes (who, what, where, damage, timeline) while discarding noise.
"""

import re
from typing import Dict, Any


class ClaimSummarizer:
    """Summarizes and compresses raw claim text into structured loss facts."""

    @staticmethod
    def compress_narrative(text: str) -> Dict[str, Any]:
        """Extract and compress loss facts from narrative text."""
        text_clean = text.strip()
        
        # Identify incident type keywords
        incident = "Auto Collision"
        if re.search(r"theft|stolen", text_clean, re.I):
            incident = "Theft"
        elif re.search(r"tree|roof|wind|storm", text_clean, re.I):
            incident = "Property Casualty"
        elif re.search(r"injury|hospital|doctor", text_clean, re.I):
            incident = "Bodily Injury"

        # Identify damage descriptors
        damage_desc = "Minor body damage"
        if re.search(r"totaled|airbag|crushed|severe", text_clean, re.I):
            damage_desc = "Severe structural loss"
        elif re.search(r"major|t-bone|highway", text_clean, re.I):
            damage_desc = "Major body impact"
        elif re.search(r"scratch|fender|bumper", text_clean, re.I):
            damage_desc = "Minor exterior cosmetic damage"

        # Police report presence
        has_police = "police" in text_clean.lower() and "no police" not in text_clean.lower()

        # Condensed factual summary (50 words or less)
        condensed = f"{incident} incident reported. Impact nature: {damage_desc}. Police report filed: {has_police}."

        return {
            "condensed_summary": condensed,
            "detected_incident": incident,
            "damage_level": damage_desc,
            "police_involved": has_police,
            "original_length": len(text),
            "compressed_length": len(condensed)
        }
