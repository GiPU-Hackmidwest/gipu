export type Limits = { cpu_threads: number; max_pixels: number; session_minutes: number };
export type Device = { id: string; owner_id: string; name: string; kind: 'browser' | 'python' | 'ios'; capabilities: string[]; enabled: boolean; online: boolean; limits: Limits; session_expires_at?: number; active_task_id?: string; earned: number; telemetry: { backend?: string; model?: string; rss_mb?: number; cpu_percent?: number; progress?: number; stage?: string } };
export type Task = { id: string; job_id: string; kind: 'image_generate' | 'image_finalize'; status: string; variant: number; width: number; height: number; price: number; attempts: number; device_id?: string; device_kind?: Device['kind']; lease_id?: string; progress: number; source_url?: string };
export type JobImage = { task_id: string; url: string; variant: number; stage: string; verified?: boolean };
export type Job = { id: string; owner_id: string; prompt: string; status: string; count: number; width: number; height: number; budget: number; reserved: number; spent: number; refunded: number; tasks: Task[]; images: JobImage[]; receipt?: { budget: number; contributor_total: number; platform_fee: number; refund: number; total_charged: number }; plan: { mode: string; explanation: string; planning?: { status: string; attempts: number } } };
export type GridEvent = { id: string | number; kind: string; message: string; created_at: number; device_id?: string; user_id?: string; job_id?: string };
// grid, username and verified are V1 fields; older coordinators omit them.
export type GridCounts = { connected: number; ready_to_create: number; ready_to_finish: number };
export type Snapshot = { user: { id: string; name: string; username?: string | null }; balance: number; reserved: number; earned: number; grid?: GridCounts; devices: Device[]; jobs: Job[]; events: GridEvent[]; ledger: { id: string; job_id: string; kind: string; amount: number; note: string; created_at: number }[]; agent: { mode: string; available: boolean }; pricing: { generate: number; finalize: number; fee: number }; server_time: number };
export type Session = { token: string; name: string; server: string; userId?: string };
export type SessionResponse = { token: string; session_id: string; user: { id: string; name: string }; balance: number };
export type SessionInfo = { id: string; client_name: string; created_at: number; last_used_at?: number; current: boolean };
export type LinkCode = { code: string; expires_at: number };
export type GridLink = { kind: 'join' | 'link'; server: string; code: string };
export type DeviceCredential = { id: string; token: string };
