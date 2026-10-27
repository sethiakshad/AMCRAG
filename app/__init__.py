"""AMCRAG - Adaptive Multimodal Corrective RAG.

Module: Document Processing & Knowledge Base Preparation (Person 1)
"""

import os

# Crucial Windows OpenMP & HuggingFace runtime settings
# Must be set before any native extensions (torch, numpy, faiss) initialize
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

__version__ = "0.1.0"
