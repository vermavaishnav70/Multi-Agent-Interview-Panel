/* ── Shared TypeScript Types ────────────────────────────────── */

export interface SessionConfig {
  job_role: string;
  job_description: string;
  difficulty: 'easy' | 'medium' | 'hard';
  voice_mode: boolean;
  max_turns: number;
  resume?: File;
}

export interface SessionResponse {
  session_id: string;
  status: string;
  job_role: string;
  difficulty: string;
  max_turns: number;
  voice_mode: boolean;
  created_at: string;
}

export interface Message {
  id: string;
  role: 'user' | 'agent';
  agent_name?: string;
  content: string;
  audio_url?: string;
  timestamp: string;
}

export interface SSEEvent {
  type:
    | 'thinking'
    | 'provider_switch'
    | 'agent_info'
    | 'token'
    | 'agent_done'
    | 'tts_ready'
    | 'session_complete'
    | 'error';
  agent?: string;
  content?: string;
  audio_url?: string;
  message?: string;
  from_provider?: string;
  to_provider?: string;
  reason?: string;
  message_id?: string;
  turn_count?: number;
  max_turns?: number;
  scorecard_ready?: boolean;
}

export interface ResumeAccuracy {
  verified_claims: string[];
  unverified_claims: string[];
  inflated_claims: string[];
}

export interface Scorecard {
  session_id: string;
  summary: string;
  strengths: string[];
  improvement_areas: string[];
  resume_accuracy: ResumeAccuracy;
  per_dimension_scores: Record<string, number>;
  final_score: number;
  hire_recommendation: 'strong_yes' | 'yes' | 'borderline' | 'no';
}

export type AgentRole = 'hr' | 'technical' | 'behavioral' | 'synthesizer';

export const AGENT_CONFIG: Record<AgentRole, { name: string; color: string; emoji: string }> = {
  hr: { name: 'HR Interviewer', color: 'var(--agent-hr)', emoji: '👔' },
  technical: { name: 'Technical Lead', color: 'var(--agent-tech)', emoji: '💻' },
  behavioral: { name: 'Behavioral Coach', color: 'var(--agent-behavioral)', emoji: '🎯' },
  synthesizer: { name: 'Panel Synthesizer', color: 'var(--agent-synthesizer)', emoji: '📊' },
};
