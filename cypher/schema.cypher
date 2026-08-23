// ====================================================================
// PROJECT REDOPS-AI - CYPHER GRAPH SCHEMA & CONSTRAINTS
// Neural Attack Matrix & Topology Database
// ====================================================================

// Node Constraints
CREATE CONSTRAINT FOR (h:Host) REQUIRE h.id IS UNIQUE;
CREATE CONSTRAINT FOR (s:Service) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT FOR (v:Vulnerability) REQUIRE v.cve_id IS UNIQUE;
CREATE CONSTRAINT FOR (u:Identity) REQUIRE u.principal IS UNIQUE;
CREATE CONSTRAINT FOR (t:Technique) REQUIRE t.mitre_id IS UNIQUE;
CREATE CONSTRAINT FOR (a:Agent) REQUIRE a.codename IS UNIQUE;

// Indexes for ultra-fast traversal
CREATE INDEX FOR (h:Host) ON (h.ip, h.zone, h.os);
CREATE INDEX FOR (s:Service) ON (s.port, s.protocol, s.version);
CREATE INDEX FOR (v:Vulnerability) ON (v.severity, v.cvss_score);
CREATE INDEX FOR (t:Technique) ON (t.tactic, t.phase);

// Initial Node Archetypes for RedOps AI
CREATE (:Agent {
    codename: 'OVERLORD-PRIME',
    role: 'KillChain Orchestrator',
    status: 'ONLINE',
    latency_ns: 120,
    specialization: 'Neural Planning & Mission Control'
});

CREATE (:Agent {
    codename: 'SPECTRE-RECON',
    role: 'Surface & Protocol Hunter',
    status: 'ONLINE',
    latency_ns: 85,
    specialization: 'Sub-ms Reconnaissance & Port Synthesis'
});

CREATE (:Agent {
    codename: 'NEXUS-CYPHER',
    role: 'Graph Topology Navigator',
    status: 'ONLINE',
    latency_ns: 45,
    specialization: 'Lateral Movement Pathfinding & Graph AI'
});

CREATE (:Agent {
    codename: 'VORTEX-EXPLOIT',
    role: 'Vuln & Flaw Synthesizer',
    status: 'ONLINE',
    latency_ns: 110,
    specialization: 'Autonomous Vulnerability Correlation'
});

CREATE (:Agent {
    codename: 'CIPHER-MORPH',
    role: 'Evasion & Obfuscation Heuristics',
    status: 'ONLINE',
    latency_ns: 32,
    specialization: 'Cython C-Speed Payload Mutation'
});

CREATE (:Agent {
    codename: 'CHRONO-DEBRIEF',
    role: 'Countermeasure Architect',
    status: 'ONLINE',
    latency_ns: 95,
    specialization: 'Real-time Remediation & Executive Intel'
});
