"""
Deterministic FAISS Vector Index Builder for FNOL Policy Corpus
Business Case ID: BC-AAIE-HACK-06 (AC-01 / Workstream F)

Reads synthetic policy documents from data/policy_corpus/, extracts structured clause metadata,
computes dense vector embeddings using SentenceTransformers (all-MiniLM-L6-v2), and constructs
a FAISS IndexFlatIP (cosine similarity index) stored in data/.
"""

import os
import sys
import glob
import re
import json
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.tools.rag_tool import PolicyRAGTool, get_policy_rag_tool


def build_faiss_index(corpus_dir: str = "data/policy_corpus", output_dir: str = "data") -> int:
    """Build or rebuild FAISS index over the policy documents."""
    print(f"[Build Index] Scanning policy documents in: {corpus_dir}")
    rag_tool = PolicyRAGTool(corpus_dir=corpus_dir)
    rag_tool._build_index()

    chunk_count = len(rag_tool.chunks)
    print(f"[Build Index] Successfully extracted {chunk_count} policy clauses.")
    if rag_tool.index is not None:
        index_file = os.path.join(output_dir, "policy_index.faiss")
        import faiss
        faiss.write_index(rag_tool.index, index_file)
        print(f"[Build Index] FAISS index written to: {index_file}")

    chunks_file = os.path.join(output_dir, "policy_chunks.json")
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(rag_tool.chunks, f, indent=2)
    print(f"[Build Index] Policy chunks saved to: {chunks_file}")

    return chunk_count


if __name__ == "__main__":
    count = build_faiss_index()
    print(f"[Build Index] Complete. Total clauses indexed: {count}")
