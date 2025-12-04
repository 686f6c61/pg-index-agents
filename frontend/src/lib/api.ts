/**
 * PG Index Agents - Cliente API
 * https://github.com/686f6c61/pg-index-agents
 *
 * Este modulo implementa el cliente HTTP para comunicarse con el backend
 * FastAPI. Proporciona tipado completo para todas las respuestas y metodos
 * para interactuar con cada endpoint de la API.
 *
 * Categorias de operaciones disponibles:
 *
 *   Gestion de bases de datos:
 *     - listDatabases, getDatabase, registerDatabase
 *     - clearResults (elimina resultados de analisis)
 *
 *   Ejecucion de agentes:
 *     - runExplorer, runObserver, runArchitect, runGardener, runPartitioner
 *     - runAllAgents (ejecuta todos en secuencia)
 *     - Versiones *Background para ejecucion asincrona con job_id
 *
 *   Gestion de propuestas:
 *     - getProposals, approveProposal, rejectProposal
 *
 *   Configuracion:
 *     - getAutonomyConfig, setAutonomyLevel
 *
 *   Monitoreo:
 *     - listJobs, getJob, cancelJob, getRunningJobsCount
 *     - healthCheck, testConnection
 *     - getAnalysisHistory, getAnalysisById, getLogs
 *
 *   Explicaciones IA:
 *     - explainItem (anomalias, senales, tareas, propuestas)
 *     - generateReportSummary
 *
 * Configuracion:
 *   La URL base se configura mediante NEXT_PUBLIC_API_URL o usa
 *   http://localhost:8000/api por defecto.
 *
 * @author 686f6c61
 * @license MIT
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface Database {
  id: number;
  name: string;
  host: string;
  port: number;
  database_name: string;
  status: string;
  created_at: string;
  last_analysis: string | null;
}

export interface TableClassification {
  name: string;
  type: string;
  criticality: string;
  characteristics: string[];
  row_count: number;
  total_size_bytes: number;
  column_count: number;
  index_count: number;
}

export interface Anomaly {
  type: string;
  severity: 'high' | 'medium' | 'low';
  table: string;
  column?: string;
  index?: string;
  indexes?: string[];
  description: string;
  recommendation?: string;
}

export interface DependencyEdge {
  from: string;
  to: string;
  type: 'foreign_key' | 'inferred';
  column: string;
}

export interface DependencyGraph {
  nodes: Record<string, {
    references: string[];
    referenced_by: string[];
    inferred: string[];
  }>;
  edges: DependencyEdge[];
}

export interface WorkPlan {
  observer_priorities: Array<{ table: string; reason: string }>;
  architect_tasks: Array<{
    type: string;
    table: string;
    description: string;
    recommendation: string;
  }>;
  gardener_tasks: Array<{
    type: string;
    table: string;
    index: string;
    action: string;
  }>;
  summary: {
    total_tables: number;
    high_criticality_tables: number;
    total_anomalies: number;
    high_severity_anomalies: number;
    medium_severity_anomalies: number;
  };
}

export interface Analysis {
  id: number;
  database_id: number;
  agent: string;
  analysis_type: string;
  result_json: {
    metadata_summary: {
      tables: number;
      indexes: number;
      foreign_keys: number;
      database_size: {
        database_name: string;
        size_bytes: number;
        size_human: string;
      };
    };
    dependency_graph: DependencyGraph;
    table_classifications: Record<string, TableClassification>;
    anomalies: Anomaly[];
    work_plan: WorkPlan;
  };
  result_markdown: string;
  created_at: string;
}

export interface Signal {
  id: number;
  database_id: number;
  signal_type: string;
  severity: string;
  description: string;
  details_json: Record<string, unknown> | null;
  detected_at: string;
  status: string;
}

export interface Proposal {
  id: number;
  database_id: number;
  signal_id: number | null;
  proposal_type: string;
  sql_command: string;
  justification: string;
  estimated_impact_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface MaintenanceTask {
  task_type: string;
  table_name: string;
  index_name: string | null;
  sql_command: string;
  priority: 'high' | 'medium' | 'low';
  reason: string;
  estimated_duration: string;
}

export interface IndexHealth {
  index_name: string;
  table_name: string;
  size_bytes: number;
  estimated_bloat_ratio: number;
  last_used: string | null;
  usage_count: number;
  needs_maintenance: boolean;
  maintenance_reason: string | null;
}

export interface ObserverResult {
  status: string;
  metrics_collected: number;
  signals_detected: number;
  signals: Signal[];
}

export interface ArchitectResult {
  status: string;
  signals_processed: number;
  proposals_created: number;
  proposals: Proposal[];
}

export interface GardenerResult {
  status: string;
  indexes_checked: number;
  indexes_needing_maintenance: number;
  maintenance_tasks: MaintenanceTask[];
  tasks_count: number;
}

export interface PartitionerResult {
  status: string;
  large_tables_analyzed: number;
  partition_candidates: number;
  recommendations_count: number;
  existing_partitions: number;
  markdown_report: string;
}

export interface AllAgentsResult {
  status: string;
  results: {
    explorer: unknown;
    observer: ObserverResult;
    architect: ArchitectResult;
    gardener: GardenerResult;
  };
}

export type AutonomyLevel = 'observation' | 'assisted' | 'trust' | 'autonomous';

export interface AutonomyConfig {
  level: AutonomyLevel;
  database_id: number | null;
  levels: Record<AutonomyLevel, string>;
}

export interface Job {
  id: string;
  database_id: number;
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_step: string | null;
  total_steps: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
}

export interface AnalysisHistoryItem {
  id: number;
  database_id: number;
  agent: string;
  analysis_type: string;
  created_at: string;
}

export interface LogEntry {
  id: number;
  database_id: number | null;
  agent: string;
  level: string;
  message: string;
  details_json: string | null;
  created_at: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Database endpoints
  async listDatabases(): Promise<Database[]> {
    return this.fetch<Database[]>('/databases');
  }

  async getDatabase(id: number): Promise<Database> {
    return this.fetch<Database>(`/databases/${id}`);
  }

  async registerDatabase(data: {
    name: string;
    host?: string;
    port?: number;
    database_name: string;
  }): Promise<Database> {
    return this.fetch<Database>('/databases', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Analysis endpoints
  async getAnalysis(databaseId: number, agent?: string): Promise<Analysis | { message: string }> {
    const params = agent ? `?agent=${agent}` : '';
    return this.fetch<Analysis | { message: string }>(`/databases/${databaseId}/analyses${params}`);
  }

  async runExplorer(databaseId: number): Promise<{
    status: string;
    summary: WorkPlan['summary'];
    anomalies_count: number;
    high_severity_count: number;
    markdown_report: string;
  }> {
    return this.fetch(`/databases/${databaseId}/analyze/explorer`, {
      method: 'POST',
    });
  }

  async runObserver(databaseId: number): Promise<ObserverResult> {
    return this.fetch(`/databases/${databaseId}/analyze/observer`, {
      method: 'POST',
    });
  }

  async runArchitect(databaseId: number): Promise<ArchitectResult> {
    return this.fetch(`/databases/${databaseId}/analyze/architect`, {
      method: 'POST',
    });
  }

  async runGardener(databaseId: number): Promise<GardenerResult> {
    return this.fetch(`/databases/${databaseId}/analyze/gardener`, {
      method: 'POST',
    });
  }

  async runPartitioner(databaseId: number): Promise<PartitionerResult> {
    return this.fetch(`/databases/${databaseId}/analyze/partitioner`, {
      method: 'POST',
    });
  }

  async runAllAgents(databaseId: number): Promise<AllAgentsResult> {
    return this.fetch(`/databases/${databaseId}/analyze/all`, {
      method: 'POST',
    });
  }

  // Autonomy configuration
  async getAutonomyConfig(databaseId?: number): Promise<AutonomyConfig> {
    const params = databaseId ? `?db_id=${databaseId}` : '';
    return this.fetch(`/config/autonomy${params}`);
  }

  async setAutonomyLevel(level: AutonomyLevel, databaseId?: number): Promise<{ status: string }> {
    const params = databaseId ? `?db_id=${databaseId}` : '';
    return this.fetch(`/config/autonomy${params}`, {
      method: 'POST',
      body: JSON.stringify({ level }),
    });
  }

  async clearResults(databaseId: number): Promise<{ status: string; deleted: Record<string, number> }> {
    return this.fetch(`/databases/${databaseId}/results`, {
      method: 'DELETE',
    });
  }

  // Signal endpoints
  async getSignals(databaseId: number): Promise<Signal[]> {
    return this.fetch<Signal[]>(`/databases/${databaseId}/signals`);
  }

  // Proposal endpoints
  async getProposals(databaseId: number): Promise<Proposal[]> {
    return this.fetch<Proposal[]>(`/databases/${databaseId}/proposals`);
  }

  async approveProposal(proposalId: number): Promise<{ message: string }> {
    return this.fetch(`/proposals/${proposalId}/approve`, {
      method: 'POST',
    });
  }

  async rejectProposal(proposalId: number): Promise<{ message: string }> {
    return this.fetch(`/proposals/${proposalId}/reject`, {
      method: 'POST',
    });
  }

  // Health check
  async healthCheck(): Promise<{
    status: string;
    database: { status: string; version?: string; error?: string };
  }> {
    const response = await fetch(`${this.baseUrl.replace('/api', '')}/health`);
    return response.json();
  }

  // Test connection
  async testConnection(): Promise<{ status: string; version?: string; error?: string }> {
    return this.fetch('/test-connection');
  }

  // Job endpoints
  async listJobs(databaseId?: number, status?: string, limit: number = 50): Promise<Job[]> {
    const params = new URLSearchParams();
    if (databaseId) params.append('db_id', databaseId.toString());
    if (status) params.append('status', status);
    params.append('limit', limit.toString());
    const queryString = params.toString();
    return this.fetch<Job[]>(`/jobs${queryString ? `?${queryString}` : ''}`);
  }

  async getJob(jobId: string): Promise<Job> {
    return this.fetch<Job>(`/jobs/${jobId}`);
  }

  async cancelJob(jobId: string): Promise<{ status: string; job_id: string }> {
    return this.fetch(`/jobs/${jobId}/cancel`, { method: 'POST' });
  }

  async getRunningJobsCount(): Promise<{ running_jobs: number }> {
    return this.fetch('/jobs/running/count');
  }

  // Analysis history
  async getAnalysisHistory(databaseId: number, agent?: string, limit: number = 20): Promise<AnalysisHistoryItem[]> {
    const params = new URLSearchParams();
    if (agent) params.append('agent', agent);
    params.append('limit', limit.toString());
    const queryString = params.toString();
    return this.fetch<AnalysisHistoryItem[]>(`/databases/${databaseId}/analyses/history${queryString ? `?${queryString}` : ''}`);
  }

  async getAnalysisById(analysisId: number): Promise<Analysis> {
    return this.fetch<Analysis>(`/analyses/${analysisId}`);
  }

  // Logs endpoint
  async getLogs(databaseId?: number, agent?: string, limit: number = 100): Promise<LogEntry[]> {
    const params = new URLSearchParams();
    if (databaseId) params.append('db_id', databaseId.toString());
    if (agent) params.append('agent', agent);
    params.append('limit', limit.toString());
    const queryString = params.toString();
    const response = await this.fetch<{ logs: LogEntry[] }>(`/logs${queryString ? `?${queryString}` : ''}`);
    return response.logs;
  }

  // Background execution versions
  async runExplorerBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/explorer?background=true`, { method: 'POST' });
  }

  async runObserverBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/observer?background=true`, { method: 'POST' });
  }

  async runArchitectBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/architect?background=true`, { method: 'POST' });
  }

  async runGardenerBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/gardener?background=true`, { method: 'POST' });
  }

  async runPartitionerBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/partitioner?background=true`, { method: 'POST' });
  }

  async runAllAgentsBackground(databaseId: number): Promise<{ status: string; job_id: string; message: string }> {
    return this.fetch(`/databases/${databaseId}/analyze/all?background=true`, { method: 'POST' });
  }

  // AI Explanation endpoints
  async explainItem(
    type: 'anomaly' | 'signal' | 'maintenance' | 'proposal',
    data: Record<string, unknown>,
    databaseId: number
  ): Promise<{ explanation: string }> {
    return this.fetch('/explain', {
      method: 'POST',
      body: JSON.stringify({ type, data, database_id: databaseId }),
    });
  }

  async generateReportSummary(databaseId: number): Promise<{ summary: string }> {
    return this.fetch(`/databases/${databaseId}/report/summary`, {
      method: 'POST',
    });
  }
}

export const api = new ApiClient();
