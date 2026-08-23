// ====================================================================
// PROJECT REDOPS-AI - LATERAL MOVEMENT CYPHER QUERIES
// Graph Pathfinding, Trust Graph Traversal & Blast Radius Calculations
// ====================================================================

// 1. Find Shortest Attack Path from Perimeter Host to Domain Controller / Core Matrix
MATCH (start:Host {zone: 'DMZ'}), (target:Host {zone: 'CORE_MATRIX'})
MATCH p = shortestPath((start)-[:CAN_ACCESS|EXPLOITS|HAS_SESSION|TRUSTS*1..8]->(target))
RETURN p, length(p) AS hops, [n IN nodes(p) | n.id] AS attack_vector;

// 2. Privilege Escalation Chain Discovery via Leaked Identities
MATCH (u:Identity)-[:MEMBER_OF*1..3]->(g:Group)
MATCH (g)-[:ADMIN_RIGHTS_ON]->(h:Host)
WHERE u.compromised = true AND h.compromised = false
RETURN u.principal AS CompromisedUser, g.name AS GroupName, h.id AS TargetHost, h.ip AS TargetIP;

// 3. Blast Radius Assessment for Target Host
MATCH (compromised:Host {compromised: true})
MATCH (compromised)-[:CAN_ACCESS|TRUSTS*1..2]->(impacted:Host)
RETURN compromised.id AS InitialFoothold, count(DISTINCT impacted) AS TotalImpactedHosts, collect(impacted.id) AS ImpactedNodeList;

// 4. Autonomous KillChain Subgraph Export
MATCH (a:Agent)-[:EXECUTED]->(step:KillChainStep)-[:TARGETS]->(h:Host)
OPTIONAL MATCH (step)-[:LEVERAGED]->(v:Vulnerability)
RETURN a.codename AS Agent, step.phase AS Phase, step.timestamp AS Timestamp, h.id AS TargetHost, v.cve_id AS VulnUsed
ORDER BY step.timestamp ASC;
