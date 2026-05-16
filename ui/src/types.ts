export type SkillStatus = 'idle' | 'running' | 'complete' | 'error'
export type Verdict = 'PURSUE' | 'WATCHLIST' | 'PASS' | 'UNKNOWN'

export interface SkillEvent {
  event: 'skill_start' | 'skill_complete' | 'skill_error'
  skill: string
  label?: string
  status?: string
  data?: Record<string, unknown>
  property_id?: string
  error?: string
}

export interface SkillState {
  name: string
  label: string
  status: SkillStatus
  data?: Record<string, unknown>
}

export interface AnalysisState {
  phase: 'idle' | 'uploading' | 'analyzing' | 'done' | 'error'
  skills: Record<string, SkillState>
  synthesisText: string
  verdict: Verdict | null
  propertyId: string | null
  errorMessage: string | null
}
