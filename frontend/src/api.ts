export type CheckStatus = "pass" | "warning" | "blocked" | "not_applicable";
export type TargetMode = "read_only" | "sim" | "real";

export interface ResolvedTargets {
  robot_profile_id?: string | null;
  robot_type?: string | null;
  robot_id?: string | null;
  robot_port?: string | null;
  robot_calibration_dir?: string | null;
  robot_calibration_revision?: string | null;
  teleoperator_profile_id?: string | null;
  teleop_type?: string | null;
  teleop_id?: string | null;
  teleop_port?: string | null;
  teleop_calibration_dir?: string | null;
  teleop_calibration_revision?: string | null;
  camera_profile_ids: Record<string, string>;
  max_relative_target?: number | null;
  action_shape: number[];
}

export interface SafetyCheck {
  code: string;
  label: string;
  status: CheckStatus;
  message: string;
}

export interface PreflightResult {
  allowed: boolean;
  requires_approval: boolean;
  checks: SafetyCheck[];
  resolved?: ResolvedTargets | null;
}

export interface Job {
  id: string;
  kind: string;
  state: string;
  target_mode: TargetMode;
  parameters: Record<string, unknown>;
  resources: Array<{ resource_id: string; resource_type: string; mode: string }>;
  requested_by: string;
  resolved_targets?: ResolvedTargets | null;
  progress: number;
  message: string;
  result: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
  approval_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Summary {
  system_status: CheckStatus;
  physical_enabled: boolean;
  devices: number;
  robots: number;
  datasets: number;
  policies: number;
  active_jobs: number;
  blocked_jobs: number;
  recent_jobs: Job[];
}

export interface DoctorCheck {
  code: string;
  label: string;
  status: CheckStatus;
  detail: string;
  remediation?: string | null;
}

export interface CapabilityManifest {
  platform_version: string;
  python_version: string;
  os: string;
  architecture: string;
  packages: Record<string, string | null>;
  accelerator: string;
  camera_backends: string[];
  robot_adapters: string[];
  policy_adapters: string[];
  simulation_backends: string[];
  physical_enabled: boolean;
}

export interface DoctorReport {
  overall: CheckStatus;
  checks: DoctorCheck[];
  capabilities: CapabilityManifest;
}

export interface Device {
  id: string;
  kind: string;
  name: string;
  stable_fingerprint: string;
  transient_path?: string | null;
  stable_path?: string | null;
  matched_profile_id?: string | null;
  matched_role?: string;
  vendor?: string | null;
  product?: string | null;
  serial_number?: string | null;
  capabilities: string[];
  health: string;
  is_simulated: boolean;
}

export interface Robot {
  id: string;
  name: string;
  product_sku: string;
  robot_type: string;
  serial_number?: string | null;
  device_fingerprint?: string | null;
  port?: string | null;
  calibration_id?: string | null;
  calibration_revision?: string | null;
  motor_layout: Record<string, number>;
  camera_mapping: Record<string, string>;
  safety_profile: Record<string, unknown>;
  supported_features: string[];
  calibration_verified: boolean;
  joint_limits_verified: boolean;
  emergency_stop_ready: boolean;
  target_mode: TargetMode;
}

export interface Teleoperator {
  id: string;
  name: string;
  product_sku: string;
  teleoperator_type: string;
  serial_number?: string | null;
  device_fingerprint?: string | null;
  port?: string | null;
  calibration_id?: string | null;
  calibration_revision?: string | null;
  target_robot_types: string[];
  target_mode: TargetMode;
}

export interface CalibrationArtifact {
  id: string;
  role: string;
  device_type: string;
  device_id: string;
  source: string;
  checksum: string;
  live_path: string;
  motors: Record<string, Record<string, number>>;
  validation_result: {
    valid?: boolean;
    motor_count?: number;
    problems?: string[];
    warnings?: string[];
  };
  supersedes?: string | null;
  created_at: string;
}

export interface SafetyStatus {
  emergency_stop_engaged: boolean;
  physical_enabled: boolean;
  default_max_relative_target: number;
  max_relative_target_ceiling: number;
  runtime_available: boolean;
}

export interface CommandPreview {
  executable: string;
  arguments: string[];
  required_parameters: string[];
  description: string;
  requires_actuation: boolean;
  interactive: boolean;
  uses_shell: boolean;
  environment: Record<string, string>;
  runtime_available: boolean;
  physical_enabled: boolean;
  execution_allowed: boolean;
  preflight: PreflightResult;
}

export interface TelemetrySample {
  kind: string;
  at: string;
  loop_ms?: number | null;
  hz?: number | null;
  joints: Record<string, number>;
  ranges: Record<string, { min: number; pos: number; max: number }>;
  prompt?: string | null;
  expects?: string | null;
  episode?: number | null;
  phase?: string | null;
  message?: string | null;
}

export interface TelemetrySummary {
  samples: number;
  p50_loop_ms?: number | null;
  p95_loop_ms?: number | null;
  joints: Record<string, number>;
  ranges: Record<string, { min: number; pos: number; max: number }>;
  prompt?: TelemetrySample | null;
  episode?: TelemetrySample | null;
  /** Present only after LeRobot itself decoded a dashboard control byte. */
  control?: TelemetrySample | null;
  /** Bounded recording lifecycle history; retained separately from loop samples. */
  events?: TelemetrySample[];
}

export interface RecordingStatus {
  job_id: string;
  job_state: string;
  requested_repo_id: string;
  recorded_repo_id?: string | null;
  root: string;
  saved_episodes: number;
  saved_frames: number;
  buffered_frames: number;
  buffered_frames_by_camera: Record<string, number>;
  fps: number;
  metadata_present: boolean;
  planned_episodes: number;
  dataset_episode_start: number;
  finalized: boolean;
}

export interface JobSnapshot {
  type: string;
  jobs: Job[];
  leases: Array<{ resource_id: string; resource_type: string; owner_job_id: string; mode: string }>;
  telemetry: Record<string, TelemetrySummary>;
}

export interface Camera {
  id: string;
  name: string;
  device_fingerprint: string;
  backend: string;
  semantic_name: string;
  width: number;
  height: number;
  fps: number;
  supports_depth: boolean;
  orientation_degrees: number;
  latency_baseline_ms?: number | null;
}

export interface Dataset {
  id: string;
  name: string;
  repo_id?: string | null;
  local_path?: string | null;
  task: string;
  calibration_revision?: string | null;
  features: string[];
  camera_mapping: Record<string, string>;
  fps: number;
  episodes: number;
  total_frames: number;
  codebase_version?: string | null;
  robot_type?: string | null;
  action_shape: number[];
  integrity_status: string;
  integrity_report?: { problems?: string[]; files?: Record<string, unknown> } | null;
  // Where the recording came from -- see PROVENANCE. Free-form on purpose: the
  // backend writes whatever the producing job knew, and a dataset recorded
  // before provenance existed carries an empty object rather than a source.
  provenance: Record<string, unknown>;
  created_at: string;
}

export interface Policy {
  id: string;
  name: string;
  policy_type: string;
  checkpoint?: string | null;
  checkpoint_step?: number | null;
  model_repo_id?: string | null;
  model_revision?: string | null;
  source_dataset_id?: string | null;
  source_repo_id?: string | null;
  expected_features: string[];
  action_shape: number[];
  camera_mapping: Record<string, string>;
  empty_cameras: number;
  runtime: string;
  training_steps?: number | null;
  compatibility_status: string;
  created_at: string;
}

export interface AgentSession {
  id: string;
  role: string;
  name: string;
  model_provider: string;
  permissions: string[];
  status: string;
}

export interface Scenario {
  id: string;
  name: string;
  robot_type: string;
  backend: string;
  scene: string;
  task: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  target: string;
  outcome: string;
}

export interface HilChecklist {
  physical_enabled: boolean;
  software_gate: string;
  checks: Array<{ id: string; label: string; status: string }>;
}

export interface MotorReading {
  motor_id: number;
  name: string;
  responded: boolean;
  model_number?: number | null;
  position?: number | null;
  volts?: number | null;
  torque_enabled?: boolean | null;
}

/** What an arm answered when we actually talked to it, not what USB claims. */
export interface DeviceIdentification {
  id: string;
  device_fingerprint?: string | null;
  port: string;
  baudrate: number;
  motors_expected: number;
  motors_found: number;
  bus_volts?: number | null;
  suggested_role: string;
  confidence: string;
  reason: string;
  motor_ids_match: boolean;
  torque_engaged: boolean;
  readings: MotorReading[];
}

export type SetupStepState = "done" | "ready" | "blocked" | "not_applicable";

export interface SetupStep {
  id: string;
  label: string;
  state: SetupStepState;
  summary: string;
  detail: string;
  evidence: Record<string, unknown>;
  blockers: string[];
  next_action?: string | null;
}

export interface SetupSlot {
  role: string;
  label: string;
  profile_id?: string | null;
  profile_name?: string | null;
  device_fingerprint?: string | null;
  device_serial?: string | null;
  port?: string | null;
  lerobot_id?: string | null;
  connected: boolean;
  calibration_revision?: string | null;
  calibration_source?: string | null;
  calibration_valid?: boolean | null;
  calibration_warnings: string[];
  motor_count: number;
  max_relative_target?: number | null;
}

export interface SetupStatus {
  commissioned: boolean;
  physical_enabled: boolean;
  slots: SetupSlot[];
  steps: SetupStep[];
  unassigned_devices: Device[];
}

const API_ROOT = "/api";

let sessionToken: string | null = null;
let sessionRequest: Promise<string> | null = null;

/**
 * The control plane hands out a per-run token so a page on another origin
 * cannot drive the robot. It also lands in a SameSite cookie, which is what
 * the MJPEG <img> and the event socket rely on.
 */
async function ensureSession(): Promise<string> {
  if (sessionToken) return sessionToken;
  sessionRequest ??= fetch(`${API_ROOT}/session`, { credentials: "same-origin" })
    .then((response) => {
      if (!response.ok) throw new Error("Oturum alınamadı");
      return response.json() as Promise<{ token: string }>;
    })
    .then((payload) => {
      sessionToken = payload.token;
      return payload.token;
    })
    .catch((error) => {
      sessionRequest = null;
      throw error;
    });
  return sessionRequest;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const send = async () => {
    const token = await ensureSession();
    return fetch(`${API_ROOT}${path}`, {
      credentials: "same-origin",
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Hashtag-Token": token,
        ...options?.headers,
      },
    });
  };

  let response = await send();
  // The token intentionally dies with the control-plane process. An already
  // open dashboard must obtain the next process's token instead of retrying
  // the stale one forever after a local restart.
  if (response.status === 401) {
    sessionToken = null;
    sessionRequest = null;
    response = await send();
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/**
 * Live job and telemetry feed. The socket reconnects on its own so a control
 * plane restart does not leave the dashboard showing a frozen arm.
 */
export function subscribeEvents(
  onSnapshot: (snapshot: JobSnapshot) => void,
  onConnectionChange?: (connected: boolean) => void,
): () => void {
  let socket: WebSocket | null = null;
  let retryTimer: number | undefined;
  let disposed = false;

  const connect = () => {
    if (disposed) return;
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    // The handshake carries the SameSite cookie set by /api/session.
    socket = new WebSocket(`${scheme}//${window.location.host}${API_ROOT}/events`);
    socket.onopen = () => onConnectionChange?.(true);
    socket.onmessage = (event) => {
      try {
        onSnapshot(JSON.parse(event.data as string) as JobSnapshot);
      } catch {
        // A malformed frame must never take the dashboard down.
      }
    };
    socket.onclose = () => {
      socket = null;
      onConnectionChange?.(false);
      if (!disposed) retryTimer = window.setTimeout(connect, 1500);
    };
    socket.onerror = () => socket?.close();
  };

  connect();
  return () => {
    disposed = true;
    if (retryTimer) window.clearTimeout(retryTimer);
    socket?.close();
  };
}

/** What the simulation can do on this machine: installed is not the same as renderable. */
export interface SimulationBackends {
  mujoco_installed: boolean;
  mujoco_renderable: boolean;
  supported: string[];
  models: string[];
  /** The mesh-accurate arm is found on disk, not shipped, so this is per-machine. */
  so101_model_available: boolean;
  so101_model_path: string | null;
  /** A window needs a desktop session; the browser stream does not. */
  viewer_available: boolean;
}

/** Whether one policy can be trained on a set of recordings at once. */
export interface DatasetComparison {
  status: "compatible" | "warnings" | "incompatible";
  summary: string;
  datasets: Array<{ id: string; name: string }>;
  blockers: Array<{ key: string; reason: string; values: Record<string, unknown> }>;
  warnings: Array<{ key: string; reason: string; values: Record<string, unknown> }>;
  profiles: Array<Record<string, unknown>>;
  total_episodes?: number;
  total_frames?: number;
}

/** One thing an agent may do here, described well enough to do it correctly. */
export interface AgentAction {
  action: string;
  summary: string;
  job_kind?: string | null;
  target_modes?: string[];
  parameters?: Record<string, string>;
  /** Keys the job blocks without, whatever mode it runs in. */
  required?: string[];
  creates_job: boolean;
  needs_human_approval: boolean;
  roles: string[];
  note?: string;
  returns?: string;
}

/** One step of a plan, with what the server says about it beside what it did. */
export interface AgentStepResult {
  index: number;
  action: string;
  /** planned | completed | blocked | failed | awaiting_human | skipped */
  state: string;
  message: string;
  command_result?: { accepted: boolean; message: string; data?: Record<string, unknown> } | null;
  brief?: AgentAction;
  warnings: string[];
}

export interface AgentPlanResult {
  plan: {
    steps: { action: string; rationale: string; parameters: Record<string, unknown> }[];
    rationale: string;
    risks: string[];
    requires_confirmation: boolean;
  };
  executed: boolean;
  steps: AgentStepResult[];
  /** Why the run stopped short. Stopping at an approval step is the normal case. */
  stopped_because: string | null;
  warnings: string[];
}

/** One exchange, kept server-side so a reload does not lose the conversation. */
export interface AgentTurn {
  id: string;
  session_id: string;
  prompt: string;
  result: AgentPlanResult;
}

/** Whether a planning model is configured, and what is missing when it is not. */
export interface PlannerStatus {
  installed: boolean;
  model_configured: boolean;
  /** The setting as written, provider prefix and all: `ollama:llama3.2:3b`. */
  model: string | null;
  /** What that setting resolved to. A bare model id means Bedrock, which is
      worth saying out loud before an operator learns it from an auth error. */
  provider: string | null;
  model_id: string | null;
  host: string | null;
  ready: boolean;
  blocked_by: string | null;
  execution_boundary: string;
  raw_robot_tools_exposed: boolean;
}

/** One take inside a recording, with the number that identifies a dead one. */
export interface DatasetEpisode {
  index: number;
  frames: number;
  task: string;
  action_range?: number | null;
  state_range?: number | null;
  demonstrates_nothing: boolean;
  /** Joints that held still for the whole take, by name. Not a fault by
   *  itself -- a task may not use the wrist -- but an episode of a grasping
   *  task where the gripper never moved is an episode where nothing was
   *  grasped. */
  still_joints?: string[];
  /** Index of the earlier episode this one is a copy of, when a merge brought
   *  the same recording in twice. Null for the first occurrence. */
  duplicate_of?: number | null;
  videos: Array<{
    camera: string;
    feature: string;
    chunk_index: number;
    file_index: number;
    from_timestamp: number;
    to_timestamp: number;
  }>;
}

export interface DatasetEpisodes {
  dataset_id: string;
  episodes: DatasetEpisode[];
  readable: boolean;
  note: string;
}

export interface PlannedEpisode {
  global_episode: number;
  game: number;
  block: string;
  instruction: string;
  board_before: string;
  after: "undo" | "leave";
  piece: string;
  target_cell: string;
}

export interface RecordingGame {
  game: number;
  block: string;
  reset_instruction: string;
  episodes: PlannedEpisode[];
}

export interface RecordingRoadmap {
  source_name: string;
  games: RecordingGame[];
  total_episodes: number;
}

export interface TicTacToeMove {
  id: string;
  piece: "X" | "O";
  object_name: string;
  cell_number: number;
  cell: string;
  task: string;
  episode_index: number;
  board_robot: string;
  board_camera: string;
  start_pose: number[];
}

export interface TicTacToeCatalogue {
  profile: string;
  policy_repo_id: string;
  policy_revision: string;
  moves: TicTacToeMove[];
}
