"""
====================================================================
PROJECT REDOPS-AI - FAST ENTROPY & SCANNER ENGINE (CYTHON BRIDGE)
Provides ultra-fast C-speed Shannon entropy and pattern matching with pure Python fallback.
====================================================================
"""

import math
from typing import List, Dict, Any

# Attempt to import compiled Cython C-extension
_CYTHON_AVAILABLE = False
try:
    from cython_core.fast_entropy_c import (
        calculate_shannon_entropy as _cy_entropy,
        fast_token_fuzz_sweep as _cy_fuzz,
        polymorphic_mutation_sim as _cy_mutation
    )
    _CYTHON_AVAILABLE = True
except ImportError:
    _CYTHON_AVAILABLE = False


def calculate_shannon_entropy(data: bytes) -> float:
    """
    Computes Shannon Entropy of a byte buffer.
    High entropy (> 7.2) indicates encrypted/obfuscated payload or packed binary.
    """
    if _CYTHON_AVAILABLE:
        return _cy_entropy(data)

    # High-performance Pure Python Fallback
    length = len(data)
    if length == 0:
        return 0.0

    counts = [0] * 256
    for b in data:
        counts[b] += 1

    entropy = 0.0
    for count in counts:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)

    return round(entropy, 4)


def fast_token_fuzz_sweep(buffer: bytes, signatures: List[str]) -> List[Dict[str, Any]]:
    """
    Fast pattern search for high-risk AST tokens, sinks, and vulnerability markers.
    """
    if _CYTHON_AVAILABLE:
        return _cy_fuzz(buffer, signatures)

    # Pure Python Fast String Pattern Matching
    matches = []
    for sig in signatures:
        sig_bytes = sig.encode('utf-8') if isinstance(sig, str) else sig
        offset = buffer.find(sig_bytes)
        if offset != -1:
            matches.append({"offset": offset, "token": sig})
    return matches


def polymorphic_mutation_sim(payload: bytes, key: int = 0x5A) -> bytes:
    """
    Simulates high-speed polymorphic byte mutation for evasion modeling.
    """
    if _CYTHON_AVAILABLE:
        return _cy_mutation(payload, key)

    mutated = bytearray(len(payload))
    for i, b in enumerate(payload):
        mutated[i] = (b ^ key) ^ ((i * 37) & 0xFF)
    return bytes(mutated)


def is_cython_accelerated() -> bool:
    return _CYTHON_AVAILABLE
