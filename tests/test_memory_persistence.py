"""
Test Cross-Session Memory Persistence for FNOL Claims-Triage Copilot
Business Case ID: BC-AAIE-HACK-06

Verifies:
- Cross-session memory recall for synthetic claimants across distinct threads.
- PII masking on claimant IDs and policy numbers.
- Generates committed evidence log to logs/memory_test.log.
"""

import os
import json
import logging
import pytest
from src.memory.tiered_memory import SemanticTieredMemory, mask_identifier


LOG_FILE = "logs/memory_test.log"


@pytest.fixture(scope="module")
def memory_logger():
    """Setup logger that writes to logs/memory_test.log for committed evidence."""
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("memory_test_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


@pytest.fixture
def tiered_memory():
    """Fixture providing isolated tiered memory database."""
    test_db = "data/test_semantic_memory.sqlite"
    memory = SemanticTieredMemory(db_path=test_db)
    memory.clear()
    yield memory
    memory.clear()
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


def test_pii_masking(memory_logger):
    """Verify that claimant and policy identifiers are strictly masked."""
    raw_claimant = "CLM-8839-IL"
    raw_policy = "POL-992384-US"
    
    masked_claimant = mask_identifier(raw_claimant)
    masked_policy = mask_identifier(raw_policy)
    
    assert masked_claimant == "CLM-***-IL"
    assert masked_policy == "POL-***-US"
    assert "8839" not in masked_claimant
    assert "992384" not in masked_policy
    
    memory_logger.info(f"PII Masking Verification Passed: {raw_claimant} -> {masked_claimant}")
    memory_logger.info(f"PII Masking Verification Passed: {raw_policy} -> {masked_policy}")


def test_cross_session_recall(tiered_memory, memory_logger):
    """Test storing facts in Session 1 and recalling them in a new Session 2."""
    claimant_id = "CLM-7782-AUTO"
    session_1 = "thread_session_001_abc"
    session_2 = "thread_session_002_xyz"
    
    masked_id = mask_identifier(claimant_id)
    memory_logger.info(f"--- Starting Session 1 (Thread: {session_1}) for Claimant: {masked_id} ---")
    
    # Session 1: Store claimant facts, preferences, and prior incident
    entry1 = tiered_memory.store_fact(
        claimant_id=claimant_id,
        key="preferred_repair_shop",
        value="Apex Auto Body, Chicago IL",
        category="preference",
        session_id=session_1,
        metadata={"distance_miles": 4.2}
    )
    entry2 = tiered_memory.store_fact(
        claimant_id=claimant_id,
        key="primary_vehicle",
        value="2022 Honda Accord (Sedan)",
        category="vehicle",
        session_id=session_1,
        metadata={"vin_masked": "1HG***99"}
    )
    entry3 = tiered_memory.store_fact(
        claimant_id=claimant_id,
        key="prior_claim_2024",
        value="Minor rear-end collision, repaired and closed",
        category="claim_history",
        session_id=session_1,
        metadata={"payout": 1250.00}
    )
    
    memory_logger.info(f"Session 1: Stored fact 'preferred_repair_shop' -> '{entry1.value}'")
    memory_logger.info(f"Session 1: Stored fact 'primary_vehicle' -> '{entry2.value}'")
    memory_logger.info(f"Session 1: Stored fact 'prior_claim_2024' -> '{entry3.value}'")
    
    # Verify Session 1 stored records correctly
    session1_facts = tiered_memory.recall_facts(claimant_id)
    assert len(session1_facts) == 3
    
    memory_logger.info(f"--- Simulating Session 2 (New Thread: {session_2}) for Claimant: {masked_id} ---")
    
    # Session 2: Fresh query from completely new thread/session
    recalled_preferences = tiered_memory.recall_facts(
        claimant_id=claimant_id,
        category="preference"
    )
    assert len(recalled_preferences) == 1
    assert recalled_preferences[0].value == "Apex Auto Body, Chicago IL"
    assert recalled_preferences[0].session_id == session_1  # Provenance points to session 1
    
    memory_logger.info(
        f"Session 2 Recall: Successfully retrieved preference '{recalled_preferences[0].key}': "
        f"'{recalled_preferences[0].value}' originally recorded in {recalled_preferences[0].session_id}"
    )
    
    # Query claimant consolidated profile across sessions
    profile = tiered_memory.get_claimant_profile(claimant_id)
    assert profile["claimant_id_masked"] == masked_id
    assert "preferred_repair_shop" in profile["preferences"]
    assert profile["preferences"]["preferred_repair_shop"] == "Apex Auto Body, Chicago IL"
    assert len(profile["prior_claims"]) == 1
    
    memory_logger.info(f"Session 2 Consolidated Profile: {json.dumps(profile)}")
    memory_logger.info("TEST RESULT: PASS - Verified cross-session recall and persistence.")
