# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
====================================================================
PROJECT REDOPS-AI - CYTHON C-SPEED ACCELERATION MODULE
High-Speed Shannon Entropy, Fast Pattern Fuzzing & Memory Scanner
====================================================================
"""

import math
from libc.math cimport log2

cpdef double calculate_shannon_entropy(const unsigned char[:] data):
    """
    Computes Shannon Entropy of a byte buffer in C-speed (sub-microsecond).
    High entropy (> 7.2) indicates encrypted/obfuscated payload or packed binary.
    """
    cdef int length = data.shape[0]
    if length == 0:
        return 0.0

    cdef int counts[256]
    cdef int i
    for i in range(256):
        counts[i] = 0

    for i in range(length):
        counts[data[i]] += 1

    cdef double entropy = 0.0
    cdef double p
    for i in range(256):
        if counts[i] > 0:
            p = <double>counts[i] / <double>length
            entropy -= p * log2(p)

    return entropy

cpdef list fast_token_fuzz_sweep(const unsigned char[:] buffer, list signatures):
    """
    C-speed pattern search for high-risk AST tokens, sinks, and vulnerability markers.
    """
    cdef int buf_len = buffer.shape[0]
    cdef list matches = []
    cdef bytes sig_bytes
    cdef const unsigned char[:] sig_view
    cdef int sig_len, i, j, found

    for sig in signatures:
        sig_bytes = sig.encode('utf-8') if isinstance(sig, str) else sig
        sig_len = len(sig_bytes)
        if sig_len > buf_len:
            continue
        
        for i in range(buf_len - sig_len + 1):
            found = 1
            for j in range(sig_len):
                if buffer[i + j] != sig_bytes[j]:
                    found = 0
                    break
            if found == 1:
                matches.append({"offset": i, "token": sig})
                break

    return matches

cpdef bytes polymorphic_mutation_sim(bytes payload, unsigned char key):
    """
    Simulates high-speed polymorphic byte mutation for evasion modeling.
    """
    cdef int length = len(payload)
    cdef bytearray mutated = bytearray(length)
    cdef const unsigned char[:] p_view = payload
    cdef int i

    for i in range(length):
        mutated[i] = (p_view[i] ^ key) ^ ((i * 37) & 0xFF)

    return bytes(mutated)
