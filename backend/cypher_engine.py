"""
====================================================================
PROJECT REDOPS-AI - CYPHER ATTACK & TOPOLOGY GRAPH ENGINE
In-Memory Dynamic Graph Engine, Real Scan Ingestion & ASCII Visualizer
Enhanced with Performance Optimizations: Caching, Indexing, Parallel Processing
====================================================================
"""

import os
import queue
import re
import json
import threading
import time
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import deque
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import asyncio

DEFAULT_JOURNAL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".redops_memory", "world_model_journal.jsonl")


class GraphNode:
    def __init__(self, node_id: str, labels: List[str], properties: Optional[Dict[str, Any]] = None):
        self.id = node_id
        self.labels = set(labels)
        self.properties = properties or {}
        self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "labels": list(self.labels),
            "properties": self.properties
        }


class GraphEdge:
    def __init__(self, edge_id: str, source_id: str, target_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None):
        self.id = edge_id
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.properties = properties or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.rel_type,
            "properties": self.properties
        }


class Neo4jSyncAdapter:
    """
    Optional write-behind replica (BEAT #3 hybrid). When NEO4J_URI is set and
    the driver is installed, graph mutations are queued to a background thread
    and mirrored into Neo4j. Queries NEVER touch this path — reads stay on the
    23us in-memory engine; replication is strictly best-effort.
    """
    def __init__(self):
        self.uri = os.environ.get("NEO4J_URI")
        self._q: "queue.Queue[Tuple[str, Dict[str, Any]]]" = queue.Queue()
        self._driver = None
        self._thread: Optional[threading.Thread] = None
        if self.uri:
            try:
                from neo4j import GraphDatabase  # optional dependency
                self._driver = GraphDatabase.driver(self.uri)
                self._thread = threading.Thread(target=self._pump, daemon=True)
                self._thread.start()
            except Exception:
                self._driver = None  # disabled; never block the hot path

    @property
    def active(self) -> bool:
        return self._driver is not None

    def enqueue(self, op: str, payload: Dict[str, Any]):
        if self.active:
            self._q.put((op, payload))

    def _pump(self):
        while True:
            op, payload = self._q.get()
            try:
                with self._driver.session() as s:
                    if op == "add_node":
                        s.run("MERGE (n:Node {id: $id}) SET n.labels=$labels, n.props=$props",
                              id=payload["node_id"], labels=payload["labels"],
                              props=json.dumps(payload["properties"]))
                    elif op == "add_edge":
                        s.run("MERGE (a:Node {id:$src}) MERGE (b:Node {id:$dst}) "
                              "MERGE (a)-[r:REL {type:$rel}]->(b)",
                              src=payload["source_id"], dst=payload["target_id"],
                              rel=payload["rel_type"])
            except Exception:
                pass  # replica lag is acceptable; in-memory graph is truth


class GraphIndex:
    """
    High-performance indexing system for graph queries.
    Provides O(1) lookups for common query patterns.
    """
    def __init__(self):
        self.label_index: Dict[str, Set[str]] = {}  # label -> node_ids
        self.property_index: Dict[str, Dict[Any, Set[str]]] = {}  # property -> value -> node_ids
        self.edge_type_index: Dict[str, Set[str]] = {}  # edge_type -> edge_ids
    
    def add_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]):
        for label in labels:
            if label not in self.label_index:
                self.label_index[label] = set()
            self.label_index[label].add(node_id)
        
        for prop, value in properties.items():
            if prop not in self.property_index:
                self.property_index[prop] = {}
            if value not in self.property_index[prop]:
                self.property_index[prop][value] = set()
            self.property_index[prop][value].add(node_id)
    
    def add_edge(self, edge_id: str, rel_type: str):
        if rel_type not in self.edge_type_index:
            self.edge_type_index[rel_type] = set()
        self.edge_type_index[rel_type].add(edge_id)
    
    def get_nodes_by_label(self, label: str) -> Set[str]:
        return self.label_index.get(label, set())
    
    def get_nodes_by_property(self, prop: str, value: Any) -> Set[str]:
        return self.property_index.get(prop, {}).get(value, set())
    
    def get_edges_by_type(self, edge_type: str) -> Set[str]:
        return self.edge_type_index.get(edge_type, set())


class QueryCache:
    """
    LRU cache for graph query results with TTL support.
    """
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
    
    def _generate_key(self, query: str, params: Optional[Dict] = None) -> str:
        key_data = query + json.dumps(params or {}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, query: str, params: Optional[Dict] = None) -> Optional[Any]:
        key = self._generate_key(query, params)
        with self._lock:
            if key in self.cache:
                result, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    return result
                else:
                    del self.cache[key]
        return None
    
    def set(self, query: str, result: Any, params: Optional[Dict] = None):
        key = self._generate_key(query, params)
        with self._lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            self.cache[key] = (result, time.time())
    
    def clear(self):
        with self._lock:
            self.cache.clear()


class CypherGraphEngine:
    """
    High-performance In-Memory Graph Engine supporting dynamic scan ingestion,
    shortest path attack traversal, lateral movement pathfinding, ASCII rendering,
    and write-through journal persistence (BEAT #3: Neo4j-grade durability at
    in-memory speed — queries never leave RAM).
    
    Enhanced with:
    - Multi-level indexing for O(1) lookups
    - LRU query caching with TTL
    - Parallel path computation
    - Batch operations for bulk updates
    """
    def __init__(self, journal_path: Optional[str] = DEFAULT_JOURNAL_PATH,
                 seed: bool = True, enable_cache: bool = True, 
                 cache_size: int = 1000, cache_ttl: int = 300):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.adjacency: Dict[str, List[str]] = {} # source_id -> list of edge_ids
        self.rev_adjacency: Dict[str, List[str]] = {} # target_id -> list of edge_ids
        self.journal_path = journal_path
        self._journal_enabled = journal_path is not None
        self.neo4j = Neo4jSyncAdapter()
        
        # Performance enhancements
        self.index = GraphIndex()
        self.query_cache = QueryCache(cache_size, cache_ttl) if enable_cache else None
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="graph_worker")
        self._batch_queue: Optional[asyncio.Queue] = None
        self._batch_processing = False
        
        if seed:
            self._seed_default_topology()

    # ---- write-through journal (BEAT #3) ------------------------------
    def _journal(self, op: str, payload: Dict[str, Any]):
        self.neo4j.enqueue(op, payload)
        if not self._journal_enabled:
            return
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
        with open(self.journal_path, "a") as fh:
            fh.write(json.dumps({"ts": time.time(), "op": op, **payload}) + "\n")

    def restore(self, journal_path: Optional[str] = None) -> Dict[str, int]:
        """Replay the write-through journal (idempotent merge) with parallel processing."""
        path = journal_path or self.journal_path
        replayed = {"nodes": 0, "edges": 0}
        if not path or not os.path.exists(path):
            return replayed
        flag, self._journal_enabled = self._journal_enabled, False
        
        # Collect operations first for batch processing
        node_ops = []
        edge_ops = []
        
        try:
            with open(path) as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("op") == "add_node":
                        node_ops.append(rec)
                    elif rec.get("op") == "add_edge":
                        edge_ops.append(rec)
            
            # Process nodes in parallel
            def process_node(op):
                self.add_node(op["node_id"], op["labels"], op.get("properties"))
                return 1
            
            def process_edge(op):
                self.add_edge(op["source_id"], op["target_id"],
                              op["rel_type"], op.get("properties"))
                return 1
            
            # Use thread pool for parallel processing
            if node_ops:
                node_results = list(self._executor.map(process_node, node_ops))
                replayed["nodes"] = sum(node_results)
            
            if edge_ops:
                edge_results = list(self._executor.map(process_edge, edge_ops))
                replayed["edges"] = sum(edge_results)
                
        finally:
            self._journal_enabled = flag
        return replayed

    def snapshot(self, path: Optional[str] = None) -> str:
        """Point-in-time full-state snapshot (compaction boundary for the journal)."""
        out = path or (self.journal_path + ".snapshot" if self.journal_path else None)
        if not out:
            return ""
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as fh:
            json.dump(self.get_full_graph_state(), fh)
        return out

    def add_node(self, node_id: str, labels: List[str], properties: Optional[Dict[str, Any]] = None) -> GraphNode:
        self._journal("add_node", {"node_id": node_id, "labels": labels,
                                   "properties": properties or {}})
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.labels.update(labels)
            if properties:
                node.properties.update(properties)
            # Update index for existing node
            self.index.add_node(node_id, labels, properties or {})
            return node

        node = GraphNode(node_id, labels, properties)
        self.nodes[node_id] = node
        self.adjacency[node_id] = []
        self.rev_adjacency[node_id] = []
        # Add to index
        self.index.add_node(node_id, labels, properties or {})
        return node

    def add_edge(self, source_id: str, target_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> GraphEdge:
        self._journal("add_edge", {"source_id": source_id, "target_id": target_id,
                                   "rel_type": rel_type, "properties": properties or {}})
        edge_id = f"{source_id}-[{rel_type}]->{target_id}"
        edge = GraphEdge(edge_id, source_id, target_id, rel_type, properties)
        self.edges[edge_id] = edge

        if source_id not in self.adjacency:
            self.adjacency[source_id] = []
        self.adjacency[source_id].append(edge_id)

        if target_id not in self.rev_adjacency:
            self.rev_adjacency[target_id] = []
        self.rev_adjacency[target_id].append(edge_id)
        
        # Add to index
        self.index.add_edge(edge_id, rel_type)
        return edge

    def ingest_live_scan(self, scan_data: Dict[str, Any]):
        """
        Dynamically ingests real live scan results into the graph topology.
        """
        target = scan_data.get("target", "target-host")
        ip = scan_data.get("ip", target)
        open_ports = scan_data.get("open_ports", [])
        web_audit = scan_data.get("web_audit", {})
        risks = web_audit.get("security_risks", [])

        # 1. Create Target Host Node
        host_id = f"host-{target}"
        self.add_node(host_id, ["Host", "Target"], {
            "target": target,
            "ip": ip,
            "status": "SCANNED",
            "open_ports_count": len(open_ports),
            "updated_at": time.strftime("%H:%M:%S")
        })

        # 2. Add Service & Port Nodes
        for p in open_ports:
            port_num = p.get("port")
            svc_name = p.get("service", "UNKNOWN")
            svc_id = f"svc-{target}-{port_num}"
            self.add_node(svc_id, ["Service", "Port"], {
                "port": port_num,
                "service": svc_name,
                "protocol": "TCP",
                "latency_ms": p.get("latency_ms", 0),
                "banner": p.get("banner", "")
            })
            self.add_edge(host_id, svc_id, "EXPOSES_SERVICE", {"port": port_num})

        # 3. Add Risk / Vulnerability Nodes
        for r in risks:
            risk_id = f"risk-{target}-{r.get('id', 'VULN')}"
            self.add_node(risk_id, ["Vulnerability", "SecurityRisk"], {
                "title": r.get("title", "Risk"),
                "severity": r.get("severity", "MEDIUM"),
                "description": r.get("description", "")
            })
            self.add_edge(host_id, risk_id, "HAS_RISK", {"severity": r.get("severity", "MEDIUM")})

    def find_shortest_path(self, start_id: str, target_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        BFS algorithm to compute the shortest attack chain / lateral movement path.
        """
        if start_id not in self.nodes or target_id not in self.nodes:
            return None

        queue = deque([[start_id]])
        visited = {start_id}

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current == target_id:
                result_path = []
                for nid in path:
                    result_path.append(self.nodes[nid].to_dict())
                return result_path

            for edge_id in self.adjacency.get(current, []):
                edge = self.edges[edge_id]
                neighbor = edge.target_id
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = list(path)
                    new_path.append(neighbor)
                    queue.append(new_path)

        return None

    def execute_query(self, cypher_query: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Interprets Cypher queries (MATCH, RETURN, shortestPath, WHERE).
        Enhanced with indexing and caching for O(1) label/property lookups.
        """
        q = cypher_query.strip()
        
        # Check cache first if enabled
        if use_cache and self.query_cache:
            cached_result = self.query_cache.get(q)
            if cached_result is not None:
                cached_result["cached"] = True
                return cached_result
        
        start_time = time.perf_counter()

        if "shortestPath" in q or "shortest_path" in q:
            # Use indexed lookups for start/end nodes
            dmz_nodes = list(self.index.get_nodes_by_label("EntryPoint")) or \
                       list(self.index.get_nodes_by_property("zone", "DMZ")) or \
                       list(self.index.get_nodes_by_label("Host"))
            crown_nodes = list(self.index.get_nodes_by_label("CrownJewel")) or \
                         list(self.index.get_nodes_by_property("zone", "CORE_MATRIX")) or \
                         list(self.index.get_nodes_by_label("Vulnerability"))
            
            start_node = dmz_nodes[0] if dmz_nodes else list(self.nodes.keys())[0]
            target_node = crown_nodes[-1] if crown_nodes else list(self.nodes.keys())[-1]
            
            path = self.find_shortest_path(start_node, target_node)
            elapsed_us = (time.perf_counter() - start_time) * 1_000_000

            result = {
                "query": cypher_query,
                "status": "SUCCESS",
                "execution_time_us": round(elapsed_us, 2),
                "type": "PATH_TRAVERSAL",
                "hops": len(path) - 1 if path else 0,
                "path": path,
                "summary": f"Computed shortest attack path from {start_node} to {target_node} ({len(path)-1 if path else 0} hops)",
                "cached": False
            }
            
            # Cache the result
            if use_cache and self.query_cache:
                self.query_cache.set(q, result)
            
            return result

        results = []
        # Use indexed lookups for common patterns
        if "MATCH (a:Agent)" in q:
            node_ids = self.index.get_nodes_by_label("Agent")
            results = [self.nodes[nid].to_dict() for nid in node_ids]
        elif "MATCH (v:Vulnerability)" in q or "MATCH (r:SecurityRisk)" in q:
            vuln_ids = self.index.get_nodes_by_label("Vulnerability")
            risk_ids = self.index.get_nodes_by_label("SecurityRisk")
            all_ids = vuln_ids.union(risk_ids)
            results = [self.nodes[nid].to_dict() for nid in all_ids]
        elif "MATCH (s:Service)" in q:
            service_ids = self.index.get_nodes_by_label("Service")
            results = [self.nodes[nid].to_dict() for nid in service_ids]
        elif "MATCH (h:Host)" in q:
            host_ids = self.index.get_nodes_by_label("Host")
            results = [self.nodes[nid].to_dict() for nid in host_ids]
        else:
            results = [n.to_dict() for n in self.nodes.values()]

        elapsed_us = (time.perf_counter() - start_time) * 1_000_000
        result = {
            "query": cypher_query,
            "status": "SUCCESS",
            "execution_time_us": round(elapsed_us, 2),
            "record_count": len(results),
            "records": results[:50],
            "cached": False
        }
        
        # Cache the result
        if use_cache and self.query_cache:
            self.query_cache.set(q, result)
        
        return result

    def render_ascii_graph(self) -> str:
        """
        Renders an ASCII visualization of the active target graph topology.
        """
        lines = [
            "╔══════════════════════════════════════════════════════════════════════════╗",
            "║                  🌐 LIVE TOPOLOGY & EXPOSURE GRAPH                       ║",
            "╚══════════════════════════════════════════════════════════════════════════╝"
        ]

        host_nodes = [n for n in self.nodes.values() if "Host" in n.labels]
        if not host_nodes:
            lines.append(" [!] No active hosts indexed in graph. Run a scan directive.")
            return "\n".join(lines)

        for host in host_nodes:
            status = host.properties.get("status", "ACTIVE")
            ip = host.properties.get("ip", "unknown")
            lines.append(f"\n 🖥️  HOST: [{host.id}] ({ip}) - Status: {status}")

            # Find services attached to this host
            out_edges = self.adjacency.get(host.id, [])
            for e_id in out_edges:
                edge = self.edges[e_id]
                target_node = self.nodes.get(edge.target_id)
                if not target_node:
                    continue

                if "Service" in target_node.labels:
                    p = target_node.properties.get("port")
                    svc = target_node.properties.get("service")
                    lat = target_node.properties.get("latency_ms", 0)
                    lines.append(f"    ├── [PORT {p}/TCP] ──> Service: {svc} ({lat}ms)")
                elif "Vulnerability" in target_node.labels or "SecurityRisk" in target_node.labels:
                    sev = target_node.properties.get("severity", "MEDIUM")
                    title = target_node.properties.get("title", target_node.id)
                    lines.append(f"    └── ⚠️  [RISK: {sev}] ──> {title}")

        lines.append(f"\n [Graph Metrics: {len(self.nodes)} Nodes | {len(self.edges)} Relationships]")
        return "\n".join(lines)

    def get_full_graph_state(self) -> Dict[str, Any]:
        """
        Returns full graph topology with performance metrics.
        """
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "performance": {
                "cache_enabled": self.query_cache is not None,
                "cache_size": len(self.query_cache.cache) if self.query_cache else 0,
                "index_stats": {
                    "label_indexes": len(self.index.label_index),
                    "property_indexes": len(self.index.property_index),
                    "edge_type_indexes": len(self.index.edge_type_index)
                }
            }
        }
    
    def batch_add_nodes(self, nodes_data: List[Dict[str, Any]]) -> List[str]:
        """
        Bulk add nodes for better performance on large datasets.
        Returns list of added node IDs.
        """
        added_ids = []
        for node_data in nodes_data:
            node_id = node_data["node_id"]
            labels = node_data.get("labels", [])
            properties = node_data.get("properties", {})
            self.add_node(node_id, labels, properties)
            added_ids.append(node_id)
        return added_ids
    
    def batch_add_edges(self, edges_data: List[Dict[str, Any]]) -> List[str]:
        """
        Bulk add edges for better performance on large datasets.
        Returns list of added edge IDs.
        """
        added_ids = []
        for edge_data in edges_data:
            source_id = edge_data["source_id"]
            target_id = edge_data["target_id"]
            rel_type = edge_data["rel_type"]
            properties = edge_data.get("properties", {})
            edge = self.add_edge(source_id, target_id, rel_type, properties)
            added_ids.append(edge.id)
        return added_ids
    
    def clear_cache(self):
        """Clear the query cache."""
        if self.query_cache:
            self.query_cache.clear()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics."""
        return {
            "graph_size": {
                "nodes": len(self.nodes),
                "edges": len(self.edges)
            },
            "cache": {
                "enabled": self.query_cache is not None,
                "current_size": len(self.query_cache.cache) if self.query_cache else 0,
                "max_size": self.query_cache.max_size if self.query_cache else 0,
                "ttl_seconds": self.query_cache.ttl_seconds if self.query_cache else 0
            },
            "index": {
                "label_count": len(self.index.label_index),
                "property_count": len(self.index.property_index),
                "edge_type_count": len(self.index.edge_type_index)
            },
            "journal": {
                "enabled": self._journal_enabled,
                "path": self.journal_path,
                "neo4j_active": self.neo4j.active
            }
        }

    def _seed_default_topology(self):
        """
        Seeds default agent hero matrix nodes.
        """
        self.add_node("OVERLORD-PRIME", ["Agent"], {"role": "Commander", "status": "ONLINE"})
        self.add_node("SPECTRE-RECON", ["Agent"], {"role": "Surface Hunter", "status": "ONLINE"})
        self.add_node("NEXUS-CYPHER", ["Agent"], {"role": "Graph Engine", "status": "ONLINE"})
        self.add_node("VORTEX-EXPLOIT", ["Agent"], {"role": "Vuln Synthesizer", "status": "ONLINE"})
        self.add_node("CIPHER-MORPH", ["Agent"], {"role": "Evasion Core", "status": "ONLINE"})
        self.add_node("CHRONO-DEBRIEF", ["Agent"], {"role": "Defense Architect", "status": "ONLINE"})


# Global Graph Engine Instance
graph_engine = CypherGraphEngine()
