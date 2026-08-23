---
name: mpc-cryptography-audit
description: Advanced Multi-Party Computation (MPC) and Threshold Cryptography security audit playbook for C, C++, Rust, and Go cryptographic libraries. Covers GG18/GG20, CMP, FROST, Lindell17, EdDSA-TSS, and proprietary MPC protocols. Target-agnostic — works on any MPC codebase.
metadata:
  subdomain: cryptography-and-mpc
  when_to_use: "mpc threshold signature gg18 gg20 cmp frost paillier zero-knowledge zkp ecdsa eddsa cryptography audit cosigner mta range proof tss multi-party"
  mitre_attack:
    - T1556
    - T1190
    - T1552.004
  languages:
    - C
    - C++
    - Rust
    - Go
---

# 🔐 MPC & Threshold Cryptography Universal Audit Playbook

This playbook is **target-agnostic** — it works on ANY Multi-Party Computation (MPC) or
Threshold Signature Scheme (TSS) codebase regardless of language, framework, or vendor.

Applicable to: Fireblocks mpc-lib, ZenGo multi-party-ecdsa, Binance tss-lib,
ING threshold-signatures, DFNS SDK, Coinbase kryptology, Taurus PROTECT, Lit Protocol,
or any custom MPC implementation.

---

## 🔍 Phase 0: Target Reconnaissance (First 30 Minutes)

Before auditing any MPC codebase, map the architecture:

### Step 1: Identify the Protocol Variant
```bash
# Search for protocol identifiers in any language
rg -i "gg18|gg20|gennaro|goldfeder" .
rg -i "cmp|canetti|maurer" .
rg -i "frost|rfc.?9591|schnorr.*threshold" .
rg -i "lindell|2p.?ecdsa|two.?party" .
rg -i "doerner|kondi|keller" .
```

### Step 2: Map the Source Tree
```bash
# Find all crypto primitives
rg -l -i "paillier|pedersen|commitments|shamir|feldman" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'
rg -l -i "range.?proof|zkp|zero.?knowledge|schnorr" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'
rg -l -i "ecrecover|secp256k1|ed25519|curve25519|p256" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'

# Find protocol round handlers (the hot path)
rg -i "round.?1|round.?2|round.?3|round.?4|phase.?1|phase.?2" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'
rg -i "mta|multiplicative.?to.?additive|mta_response|mta_request" .
```

### Step 3: Find Entry Points & Wire Types
```bash
# Message/request types — these are what an attacker controls
rg -i "struct.*request|struct.*response|struct.*message|struct.*proof" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'
rg -i "deserialize|from_bytes|decode|unmarshal|parse" . --type-add 'code:*.{c,cpp,rs,go,h,hpp}'
```

---

## 🎯 Bug Class 1: Missing or Weak Zero-Knowledge Range Proofs in MtA

**Applies to:** GG18, GG20, CMP, Lindell17, any protocol using Paillier-based MtA.

**The vulnerability:** During threshold signing, parties compute $k_i \cdot w_j$ via
Paillier homomorphic encryption. Party $j$ sends $c = \text{Enc}(w_j)$ to Party $i$.
If Party $j$ does NOT provide a Zero-Knowledge Range Proof that $|w_j| < q$ (curve order),
the attacker can send $c = \text{Enc}(a)$ where $a \gg q$, causing partial signatures
to leak $w_j \pmod{p}$ for small primes $p$ dividing $N$.

**Impact:** Full private key extraction in ~16 signing attempts.

**How to find it:**
```bash
# Find MtA computation code
rg -i "mta|multiplicative.?to.?additive|homomorphic.?mul|paillier.*mul" .

# Find range proof verification calls
rg -i "verify.*range|range.*verify|verify.*zkp|zkp.*verify|check.*proof" .

# RED FLAG: If MtA computation exists but range proof verification is missing or
# conditional (behind an if/flag), this is a Critical vulnerability.
```

**Audit checklist:**
- [ ] Every MtA response received from a peer passes through a range proof verifier
- [ ] The range proof bounds are tight: $|x| < q \cdot 2^{\ell+\epsilon}$ where $\ell, \epsilon$ are security parameters
- [ ] No code path (error handling, timeout, debug mode) skips proof verification
- [ ] The hiding factor / statistical security parameter meets minimum bounds (typically $\geq 80$ bits)

---

## 🎯 Bug Class 2: Fiat-Shamir Transcript Binding Failures

**Applies to:** ALL MPC protocols that use non-interactive zero-knowledge proofs.

**The vulnerability:** When converting interactive ZK proofs to non-interactive (via
Fiat-Shamir heuristic), the challenge hash MUST bind ALL of:
- Prover identity (party ID)
- Verifier identity
- Session identifier (signing session / txid)
- ALL commitment values and public parameters
- A domain separation salt unique to the proof type

If ANY of these are missing, the proof can be:
1. **Replayed** across sessions (missing session ID)
2. **Transferred** between parties (missing party IDs)
3. **Weakened** by parameter substitution (missing public params)

**How to find it:**
```bash
# Find Fiat-Shamir challenge computation
rg -i "fiat.?shamir|challenge|hash.*transcript|transcript.*hash" .
rg -i "SHA256_Update|sha2|blake2|keccak|hasher.*update" .

# Find salt/domain separation strings
rg '"[A-Z].*[Zz][Kk][Pp]|[Pp]roof|[Rr]ange|[Ss]alt' .

# Check: are party IDs, session IDs, and ALL proof fields included in the hash?
```

**Audit checklist:**
- [ ] Hash includes: prover_id, verifier_id, session_id/txid
- [ ] Hash includes: ALL commitment values (A, B, S, T, E, F, etc.)
- [ ] Hash includes: ALL public parameters (Paillier $N$, Ring-Pedersen $\hat{N}, s, t$)
- [ ] Salt strings are unique per proof type (no reuse across different ZKP types)
- [ ] BigNum serialization uses fixed-width padding (no variable-length encoding that could be ambiguous)

---

## 🎯 Bug Class 3: Paillier Modulus Validation

**Applies to:** Any protocol using Paillier encryption (GG18, GG20, CMP, Lindell17).

**The vulnerability:** Each party generates a Paillier keypair $N = p \cdot q$ during setup.
A malicious party could generate $N$ with:
- Small prime factors (enabling factorization and key recovery)
- $N = p^2 \cdot q$ (not square-free — breaks homomorphic properties)
- $p \not\equiv 3 \pmod{4}$ (not a Blum modulus — enables certain attacks)

**How to find it:**
```bash
# Find Paillier key generation
rg -i "paillier.*gen|gen.*paillier|new.*paillier|paillier.*key" .

# Find modulus validation / factorization proofs
rg -i "factorization.*proof|blum.*modulus|no.?small.?factor|square.?free" .
rg -i "coprime.*zkp|biprime|safe.?prime" .
```

**Audit checklist:**
- [ ] Key generation includes a ZKP of correct Blum modulus
- [ ] Verifier checks: $N$ has no small factors (trial division or ZKP)
- [ ] Verifier checks: $\gcd(N, \phi(N)) = 1$
- [ ] Statistical security parameter for Blum modulus proof $\geq 64$ bits (ideally $\geq 80$)
- [ ] The verifier does NOT accept prover-chosen auxiliary parameters without proof

---

## 🎯 Bug Class 4: Elliptic Curve Point Validation

**Applies to:** ALL MPC protocols (every protocol exchanges EC points).

**The vulnerability:** A malicious party sends an invalid curve point that:
1. Lies on the quadratic twist of the curve (different group order)
2. Is the point at infinity $\mathcal{O}$
3. Has small subgroup order (especially on curves with cofactor $> 1$ like Ed25519, $h=8$)

**How to find it:**
```bash
# Find point deserialization / receipt from wire
rg -i "from.?bytes|deserialize.*point|decode.*point|unmarshal.*point|point.*from|bn2point" .

# Find (or confirm absence of) validation
rg -i "is.?on.?curve|on.?curve|validate.*point|check.*point|is.?infinity|cofactor" .

# RED FLAG: deserialization without adjacent validation call
```

**Audit checklist:**
- [ ] Every received point verified: on correct curve, not infinity, correct order
- [ ] Ed25519: cofactor check or multiply-by-cofactor before use
- [ ] Stark curve: field-specific validation
- [ ] Compressed point decompression checks both $y$ candidates

---

## 🎯 Bug Class 5: Nonce Bias & Leakage

**Applies to:** ALL threshold ECDSA/EdDSA/Schnorr protocols.

**The vulnerability:** The collective nonce $k$ (or its shares $k_i$) must be
uniformly random. If ANY party can bias even a few bits of $k$:
- $b$ biased bits → key recoverable from $\approx 256/b$ signatures via lattice attacks (LLL/BKZ)

**How to find it:**
```bash
# Find nonce generation
rg -i "nonce|ephemeral|random.*k\b|k_share|gamma|rho" .

# Find PRNG usage
rg -i "RAND_bytes|getrandom|urandom|OsRng|crypto/rand|randombytes" .

# Find commitment schemes for nonces
rg -i "commit.*nonce|nonce.*commit|decommit" .
```

**Audit checklist:**
- [ ] Nonce shares generated from CSPRNG, not `rand()` or weak PRNG
- [ ] Commitment-then-decommitment protocol for nonce shares (Round 1: hash, Round 2: open)
- [ ] Decommitment strictly verified before nonce is used in computation
- [ ] No timing or error-message side channel leaks nonce bits

---

## 🎯 Bug Class 6: Protocol State Machine & Round-Ordering Attacks

**Applies to:** ALL multi-round MPC protocols.

**The vulnerability:** MPC protocols have strict round ordering (Round 1 → 2 → 3 → ...).
If the implementation doesn't enforce this:
- Replaying Round 2 messages from Session A into Session B
- Sending Round 3 messages before Round 2 completes
- Aborting mid-protocol to extract partial information (Lindell17 abort attack)

**How to find it:**
```bash
# Find state/round management
rg -i "round|phase|state.*machine|current.*round|expected.*round" .
rg -i "session.*id|txid|signing.*id|request.*id" .

# Find abort/timeout handling
rg -i "abort|timeout|cancel|cleanup|rollback" .
```

**Audit checklist:**
- [ ] Each round handler validates that the previous round completed
- [ ] Session IDs are unique and cannot be reused
- [ ] Abort does NOT leak partial computational results (check what gets logged/returned)
- [ ] Concurrent sessions are isolated (no shared mutable state between signing sessions)

---

## 🎯 Bug Class 7: Memory Safety (C/C++ Specific)

**Applies to:** C and C++ MPC implementations.

**Critical patterns to search for:**
```bash
# Stack allocation with attacker-influenced size
rg "alloca\(" . --type c --type cpp

# memcpy with variable/wire-controlled lengths
rg "memcpy\(" . --type c --type cpp | head -50

# OpenSSL BIGNUM exhaustion (BN_CTX_get returns NULL)
rg "BN_CTX_get" . --type c --type cpp

# malloc without NULL check
rg "malloc\(" . --type c --type cpp

# Integer overflow in size calculations
rg "size.*\+.*size|len.*\+.*len|offset.*\+.*length" . --type c --type cpp

# Use-after-free in cleanup/destructor paths
rg "free\(|delete |\.reset\(\)" . --type c --type cpp
```

**Audit checklist:**
- [ ] All `BN_CTX_get()` return values checked for NULL
- [ ] All `malloc()` return values checked for NULL
- [ ] No `alloca()` with sizes derived from wire data
- [ ] Length fields from wire validated before use in `memcpy`/allocation
- [ ] Cleanup paths don't access freed objects (especially in async/callback patterns)

---

## 🎯 Bug Class 8: Side-Channel & Timing Leaks

**Applies to:** ALL cryptographic implementations.

```bash
# Find branching on secrets
rg -i "if.*secret|if.*private|if.*key.*>>|if.*share" . --type-add 'code:*.{c,cpp,rs,go}'

# Find non-constant-time comparisons
rg "memcmp|strcmp|==.*secret|secret.*==" . --type-add 'code:*.{c,cpp,rs,go}'

# Find constant-time primitives (GOOD signs)
rg -i "constant.?time|ct_eq|CRYPTO_memcmp|subtle\.ConstantTime|BN_FLG_CONSTTIME" .
```

**Audit checklist:**
- [ ] Scalar multiplication uses constant-time algorithms (Montgomery ladder, fixed-window)
- [ ] Secret comparisons use `CRYPTO_memcmp` or equivalent, never `memcmp`
- [ ] No early-return on secret-dependent conditions
- [ ] OpenSSL BIGNUMs handling secrets have `BN_FLG_CONSTTIME` flag set

---

## 🔬 Full Audit Workflow Summary

```
PHASE 0: RECON (30 min)
├── Identify protocol variant (GG18/GG20/CMP/FROST/Lindell/custom)
├── Map source tree, find crypto primitives, protocol handlers, wire types
└── Build project, run existing test suite to understand expected behavior

PHASE 1: ZKP COMPLETENESS (4-8 hours) — HIGHEST ROI
├── For every proof generator, find the corresponding verifier
├── Check Fiat-Shamir transcript completeness
├── Check range proof bounds and statistical security params
└── Check: no code path skips verification

PHASE 2: CURVE & MATH CORRECTNESS (2-4 hours)
├── Point validation on all received EC points
├── Scalar reduction (mod q) after every arithmetic operation
├── Nonce generation quality and commitment binding
└── Paillier modulus validation

PHASE 3: PROTOCOL LOGIC (4-8 hours)
├── Round ordering enforcement
├── Session isolation and replay prevention
├── Abort behavior (information leakage on abort)
└── Multi-tenancy / key isolation

PHASE 4: IMPLEMENTATION SAFETY (2-4 hours)
├── Memory safety (C/C++): buffer overflows, UAF, integer overflows
├── Serialization: length validation before use
├── Side channels: constant-time operations
└── Error handling: what gets logged/returned on failure

PHASE 5: REPORTING
├── Map each finding to CWE + CVSS 4.0
├── Write minimal PoC (C++ test, Foundry script, or Python)
└── Submit via platform (Bugcrowd/HackerOne/Immunefi)
```

---

## 🏆 Historical Vulnerabilities Reference

| Vulnerability | Year | Affected | Impact | Root Cause |
|---|---|---|---|---|
| Alpha-Ray | 2023 | GG18/GG20 vendors | Full key extraction ~16 sigs | Missing ZK range proofs in MtA |
| BitGo TSS | 2023 | BitGo 2-of-2 | Full key recovery | No range proof on Paillier ciphertext |
| Lindell17 Abort | 2023 | 2P-ECDSA | Key extraction ~200 aborts | 1-bit leak per signing abort |
| Curv Twist | 2020 | secp256k1 MPC | Key share leakage | Points on twist accepted |
| CMP Ring-Pedersen | 2024 | CMP implementations | Weakened ZKP soundness | Prover-chosen params accepted |
| Multichain | 2023 | Bridge TSS | $126M loss | Over-broad signature acceptance |

---

## 📊 CVSS & Bounty Scoring Guide

| Finding | CVSS 4.0 | Typical Bounty |
|---|---|---|
| Missing range proof → key extraction | 9.8 Critical | $50k - $100k+ |
| Fiat-Shamir transcript incomplete | 8.5 High | $10k - $50k |
| Invalid curve point accepted | 8.0 High | $10k - $30k |
| Paillier small-factor not validated | 7.5 High | $5k - $20k |
| Buffer overflow in proof parsing | 7.0 High | $5k - $15k |
| Round replay / state machine bypass | 6.5 Medium | $2k - $10k |
| Non-constant-time scalar ops | 5.0 Medium | $1k - $5k |
| Missing NULL check / minor memory | 4.0 Medium | $500 - $2k |
