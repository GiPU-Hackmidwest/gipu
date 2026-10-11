# PocketGrid prototype protocol (v1)

All routes `/api`, JSON unless GET image. Coordinator default http://127.0.0.1:8787. Vite port 5173 proxies /api. ISO times replaced by Unix seconds in JSON. All credits are integer sandbox units, no cash value. Jobs and generated images are visible to members of this invite-only demo grid. Never send private inputs.

## Identity
- POST `/sessions` `{name,join_code}` -> `{token,user:{id,name},balance:100}`. Join code env POCKETGRID_JOIN_CODE defaults `pocketgrid-demo` for local. Store bearer token locally.
- All UI requests use `Authorization: Bearer <session token>`.
- POST `/devices` `{name,kind:"browser"|"python"|"ios",capabilities:["image_generate"|"image_finalize"],limits:{cpu_threads:2,max_pixels:262144,session_minutes:30}}` -> `{device,token}`. Device begins enabled:false. Owner session required; token is separate device credential.
- PATCH `/devices/{id}` owner session `{enabled?:bool,limits?:{cpu_threads,max_pixels,session_minutes}}`. Enabling starts timed contribution session. Disabling revokes active lease immediately (worker must cancel). Thread limit applies CPU only, no claim of GPU%/RAM enforcement.

## Snapshot UI (poll ~2 sec)
GET `/state` -> `{user:{id,name},balance,reserved,earned,devices:[Device],jobs:[Job],events:[Event],ledger:[Ledger],agent:{mode,available},pricing:{generate:6,finalize:1,fee:1},server_time}`.
Device `{id,owner_id,name,kind,capabilities,enabled,online,limits,session_expires_at,last_seen,active_task_id,telemetry:{backend?,model?,rss_mb?,cpu_percent?,progress?,stage?},earned}`. Session expiry/last_seen may null.
Job `{id,owner_id,prompt,status:"planning"|"queued"|"running"|"completed"|"cancelled"|"failed",count,width,height,steps,budget,reserved,spent,refunded,created_at,tasks:[Task],images:[{task_id,url,variant,stage}],receipt?:{budget,contributor_total,platform_fee,refund,total_charged},plan:{mode,explanation}}`.
Task `{id,job_id,kind:"image_generate"|"image_finalize",status:"queued"|"running"|"completed"|"cancelled",variant,prompt,width,height,steps,seed,price,attempts,device_id?,lease_id?,lease_expires_at?,progress,source_url?,source_task_id?,output_url?}`. Live lease IDs are only in worker claim replies, never public snapshots. finalize output dimensions exactly same as input dimensions; apply deterministic 4px teal RGB(36,203,166) frame inside all four edges to mark accepted/exported image. Generate max 512x512 default256; finalize actual pixel operation, not AI.
Event `{id,kind,message,created_at,device_id?,job_id?,user_id?}`. Only relevant events returned (own activity + public job lifecycle). Kinds include job_planning,job_created,task_started,credits_earned,task_reassigned,job_completed,job_failed,job_cancelled,device_paused.
Ledger `{id,job_id,kind,amount,created_at,note}`. Positive increases own spendable balance, negative decreases. Reserve is debit; accepted tasks transfer from escrow; unused returns at completion/cancellation. Do not infer balances by summing visible rows.

## Jobs
- POST `/jobs` owner `{prompt,count:1,width:256,height:256,steps:12,budget:10,request_id:"unique-uuid",use_agent:false}` -> Job. count1..4; dimensions256/384/512; steps4..30. Idempotency on(owner,request_id). Quote = count*7+1 minimum. Reserve full user budget, tasks cost6+1 each, one platform fee1 on successful completion. Guard fixed costs on server even if agent proposes differently. Agent optional Strands Bedrock mode; explicit errors when unavailable, no silent imitation.
- With `use_agent:true`, POST `/jobs` returns promptly with `status:"planning"`, the budget already reserved and `tasks:[]`; it does not wait for the model. A background planner durably claims the request (`plan.planning:{status,attempts,claim_id,started_at}`), runs Strands and either queues tasks (`planning.status:"done"`, job `queued`) or fails the job with a full refund (`planning.status:"failed"`, `plan.dispatch_error` names the error type only). Poll `/state` or GET `/jobs/{id}` for the outcome. Repeating the same `request_id` at any point returns the same job; it never reserves twice. A planning claim lasts 150 s; after a coordinator restart an expired claim is retried, at most three attempts, then refunded. A plan from an expired or replaced claim is rejected. If the server's planner configuration changes before planning, the job fails and is refunded rather than silently running in manual mode. 503 (no reservation) when Strands or its provider credentials are not configured. Manual jobs still return `queued` immediately.
- POST `/jobs/{id}/cancel` owner -> Job, releases remaining escrow; completed work remains paid, no fee for cancelled job. Allowed while `planning`: the full budget is refunded and a later planner submission is rejected.
- GET `/jobs/{id}` -> Job (grid session or device token).
- GET `/images/{artifact_id}` requires session OR device bearer token; returns PNG. UI fetch blob with token (do not put bearer in URLs). Source URL relative `/api/images/...`.

## Workers
All worker requests bearer device token. Persist device id/token across restarts. Auto-share only after explicit owner start (enabled persisted until session expiry).
- POST `/devices/{id}/heartbeat` `{telemetry:{...},task_id?:string,lease_id?:string}` -> `{device,lease_valid:bool}`. Every3s. Renews matching live lease to now+15s. Stop active computation when enabled:false or lease_valid:false. When idle omit task/lease and ignore false.
- POST `/devices/{id}/claim` `{}` -> `{task:Task|null,device:Device}`. max one task/device. Claims only enabled, unexpired session, matching capability+max_pixels. Server returns active existing task for idempotent repeats.
- POST `/tasks/{id}/progress` `{lease_id,progress:0..1,stage:"..."}` -> `{ok:true}` (409 stale lease).
- POST `/tasks/{id}/complete` `{lease_id,png_base64,metrics:{backend?,model?,elapsed_seconds?}}` -> `{accepted:true,duplicate:bool,earned:price}`. server verifies lease, PNG decode/size; finalize border and interior pixel equality vs source; settle exactly once. No semantic-proof claim for generated images.
- POST `/tasks/{id}/fail` `{lease_id,error}` -> `{ok:true}`; retries bounded, excludes just-failed device for next attempt. Expired/revoked leases reassigned; no credits for partial work. Retrying full image generation restarts that image, not a diffusion checkpoint.

## Agent routing and review
Strands jobs also expose `plan.routes` (stage → selected device IDs), `routing_until`, recorded `tools`, and optional `task_routes`, `review` and `reviews`. Initial choices must name enabled, online devices capable of that stage and image size. Preferences last45seconds and are bypassed when no selected worker is available. Finalization receives a fresh window when generation finishes. A failed attempt clears its old preference so healthy fallback workers can claim. Workers use the same claim API; they do not execute model-generated code.

Failure and terminal events trigger a separate background review in the configured provider mode. The agent inspects current tasks, attempts, output references and receipts. It may change preferences for exactly the queued task/attempt set it inspected; stale changes and expired or replaced review claims are rejected. Terminal receipts and completed work are immutable. Each review has a durable150second claim and at most three attempts. Events include `routing_applied`, `routing_updated`, `agent_reviewed` and `agent_review_failed`. Manual mode never invokes a model.

## Apps
Browser/iOS advertise image_finalize only, execute foreground work and cancel on Pause/background. Python worker supports both, preferring generation. All clients show limits, active task, progress, credits, in-app events. Native notification opt-in only on user tap. The Mac Tauri UI controls a paired Python worker through the coordinator; launch the worker separately using its CLI. Do not claim browser runs diffusion.
