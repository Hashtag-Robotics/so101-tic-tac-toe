# Workflow Kataloğu

Bu doküman, dashboard ve API'nin çalıştırdığı kalıcı işlerin gerçek sözleşmesini
tanımlar.

## 1. Ortak job yaşam döngüsü

```text
created
  → validating
  → blocked
  → awaiting_confirmation
  → queued
  → starting
  → running
  → stopping
  → completed | failed | aborted | interrupted
```

Her job:

- Target mode
- Requested-by identity
- Typed parameters
- Resource requests
- Progress
- Result/error
- Correlation ID
- Approval ID
- Timestamp

taşır.

## 2. Ortak execution sırası

```text
command
  → deterministic preflight
  → approval gerekiyorsa bekle
  → resource lease
  → worker execution
  → heartbeat/progress
  → artifact/result
  → lease release
  → audit
```

## 3. Target mode

| Mode | Anlamı |
|---|---|
| `read_only` | Fiziksel kaynak okuyabilir, actuation yapamaz |
| `sim` | Safe mock veya doğrulanmış sim adapter |
| `real` | HIL gate, LeRobot runtime ve confirmation zorunlu |

## 4. Job kataloğu

### `hardware_discovery`

Read-only serial device ve safe simulation/compute inventory üretir.

Çıktı:

- Device ID
- Stable fingerprint
- Transient port
- Vendor/product
- Capability
- Health

### `motor_setup`

LeRobot `lerobot-setup-motors` contract'ı.

Real parametre:

```text
role: robot | teleoperator
robot_port / robot_id
teleop_port / teleop_id
```

Physical approval zorunludur.

### `calibration`

LeRobot `lerobot-calibrate` contract'ı. Gerçek çalışmada önce calibration backup
ve hedef profile doğrulaması gerekir.

### `camera_preview`

Kamera profile, frame timing ve semantic key kontrolü. Şu anda safe mock
contract; gerçek kamera HIL sırasında açılacak.

### `teleoperation`

Sim modunda bounded safe workflow. Real modda:

- `lerobot-teleoperate`
- follower/leader exclusive lease
- calibration/joint-limit/E-stop verification
- physical enable
- approval

zorunlu.

### `recording`

Sim modunda DatasetManifest üretir. Real modda:

- `lerobot-record`
- robot ve teleoperator
- dataset `repo_id`
- task
- episode/time/reset
- kamera mapping

kullanır.

### `replay`

Dataset episode action'larını hedef robota uygular. Real modda action shape,
calibration ve approval olmadan başlamaz.

### `dataset_validate`

Dataset manifest ve feature schema doğrular. Physical kaynak kullanmaz.

### `dataset_transform`

Immutable source revision sonrası split/merge/edit gibi işlemler için ayrılmış
contract. İlk baseline safe mock'tur.

### `training`

İki runtime:

- `safe-mock`: Control plane ve artifact lifecycle testi.
- `lerobot-local`: `lerobot-train` typed subprocess.

Gerçek LeRobot training için:

```text
repo_id
policy_type
output_dir
job_name
device
steps
wandb
```

parametreleri kullanılır.

### `evaluation`

Sim modunda episode result distribution üretir. Real modda
`lerobot-rollout` ve physical gates kullanılır.

### `policy_rollout`

Policy path, processor/feature mapping ve hedef robot doğrulaması gerekir.

### `simulation`

Backend:

- `safe-mock`
- `mujoco`

MuJoCo contract modeli altı joint, position actuator, front camera ve joint
range kontrolü içerir.

### `remote_inference_probe`

Network access yapmadan:

- TLS scheme
- transport
- version/policy contract
- latency budget shape

doğrular.

### `hub_sync`

Artifact sync yaşam döngüsü için contract. Credential ve gerçek Hub transferi
sonraki doğrulama işidir.

### `diagnostics`

Doctor, job, audit ve safety bilgisini secret redaction ile destek payload'ına
çevirir.

## 5. Agent command workflow'ları

### Lab Assistant

```text
inspect_lab
inspect_jobs
prepare_discovery
```

### Dataset Curator

```text
inspect_datasets
prepare_dataset_validation
prepare_recording
```

### Training Advisor

```text
inspect_datasets
inspect_policies
prepare_training
```

### Evaluation Analyst

```text
inspect_policies
prepare_evaluation
```

### Robot Operator

```text
inspect_lab
prepare_teleoperation
prepare_recording
request_rollout
stop_job
```

Agent command kendi başına execution değildir. Gateway rolü doğrular ve normal
JobCoordinator'a typed request gönderir.

## 6. Strands plan workflow'u

```text
prompt
  → Strands Agent
  → AgentPlan structured output
  → role allowlist
  → kullanıcı review
  → opsiyonel AgentGateway execution
  → normal safety/job pipeline
```

Strands Agent:

- Tool almaz.
- Raw robot görmez.
- Shell görmez.
- Execution yapıldı iddiasında bulunamaz.

## 7. Dashboard/API eşlemesi

| Dashboard | Ana API |
|---|---|
| Overview | `/api/summary`, `/api/jobs` |
| Robot Lab | `/api/devices`, `/api/robots`, `/api/cameras` |
| Operate | `/api/jobs` |
| Dataset | `/api/datasets`, `/api/jobs` |
| Training | `/api/policies`, `/api/jobs` |
| Agents | `/api/agents/sessions`, `/api/agents/commands`, `/api/agents/plan` |
| Simulation | `/api/simulation/scenarios`, `/api/remote/endpoints` |
| Activity | `/api/jobs`, `/api/audit` |
| System | `/api/system/doctor`, `/api/system/hil-checklist` |

OpenAPI:

```text
http://127.0.0.1:8765/docs
```
