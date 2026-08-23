/**
 * REDOPS-AI - TypeScript Definitions for Swarm Matrix
 */

export interface AgentStatus {
    codename: string;
    role: string;
    status: 'IDLE' | 'SCANNING' | 'COMPUTING' | 'SYNTHESIZING' | 'MUTATING' | 'REPORTING' | 'EXECUTING';
    color_hex: string;
    specialization: string;
    log_count: number;
    latest_log?: AgentLogEntry;
}

export interface AgentLogEntry {
    timestamp: string;
    agent: string;
    level: string;
    text: string;
    meta?: Record<string, any>;
}

export interface AgentMessagePacket {
    message_id: string;
    source_agent: string;
    target_agent: string;
    event_type: string;
    content: string;
    meta: Record<string, any>;
    timestamp_ns: number;
    latency_ms: number;
}

export interface GraphNodeData {
    id: string;
    labels: string[];
    properties: Record<string, any>;
    x?: number;
    y?: number;
}

export interface GraphEdgeData {
    id: string;
    source: string;
    target: string;
    type: string;
    properties: Record<string, any>;
}

export interface CypherQueryResult {
    query: string;
    status: string;
    execution_time_us: number;
    summary?: string;
    records?: any[];
    hops?: number;
    path?: GraphNodeData[];
}
