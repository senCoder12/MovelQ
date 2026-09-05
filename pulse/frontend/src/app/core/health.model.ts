export interface AgentHealth {
  status: string;
  service: string;
  version: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  agent: AgentHealth;
}
