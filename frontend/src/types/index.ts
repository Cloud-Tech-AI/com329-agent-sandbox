export enum EventType {
  TOOL = 'tool',
  THINKING = 'thinking',
  FILE_CHANGE = 'file_change',
  DIFF = 'diff',
  DONE = 'done',
  ERROR = 'error',
  INFO = 'info',
  METRICS = 'metrics',
}

export enum Runtime {
  RUNC = 'runc',
  GVISOR = 'gvisor',
}

export interface AgentEvent {
  type: EventType
  text: string
  metadata?: Record<string, any>
  timestamp: string
}

export interface RunMetrics {
  duration_seconds: number
  tokens_used?: number
  files_changed: number
  tools_called: number
  errors: number
}

export interface DemoScenario {
  id: string
  name: string
  description: string
  repo: string
  task: string
  category: string
  estimated_duration: string
  difficulty: string
}

export interface RunRequest {
  github_repo: string
  task: string
  runtime?: Runtime
}

export interface RunResponse {
  id: string
  runtime?: Runtime
  dual_mode: boolean
}
