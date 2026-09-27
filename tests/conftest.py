import os
import pytest
from src.memory.tiered_memory import SemanticTieredMemory

@pytest.fixture(autouse=True)
def clean_test_semantic_memory(request):
    """Ensures each unit test starts with clean semantic memory so tests do not cross-contaminate."""
    test_db = f"data/test_memory_{os.getpid()}.sqlite"
    os.environ["SEMANTIC_MEMORY_DB"] = test_db
    mem = SemanticTieredMemory(db_path=test_db)
    mem.clear()
    yield
    try:
        mem.clear()
        if os.path.exists(test_db):
            os.remove(test_db)
    except Exception:
        pass

