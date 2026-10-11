//! Launch only an existing local worker environment, after an explicit Connect.
//! Worker output is never returned verbatim: it may contain credentials or URLs.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    io::Read,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{mpsc, Mutex, MutexGuard},
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager, State};
use url::Url;

const MAX_OUTPUT_LINE: usize = 4096;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(300);

#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum WorkerPhase {
    Stopped,
    Starting,
    Connected,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkerStatus {
    phase: WorkerPhase,
    #[serde(skip_serializing_if = "Option::is_none")]
    device_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    backend: Option<String>,
    message: String,
}

impl Default for WorkerStatus {
    fn default() -> Self {
        Self {
            phase: WorkerPhase::Stopped,
            device_id: None,
            backend: None,
            message: "Local image worker is disconnected.".into(),
        }
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkerDefaults {
    project_root: String,
}

#[derive(Default)]
pub struct WorkerManager(Mutex<WorkerRuntime>);

impl WorkerManager {
    fn lock(&self) -> MutexGuard<'_, WorkerRuntime> {
        self.0.lock().unwrap_or_else(|error| error.into_inner())
    }

    pub fn disconnect(&self) -> WorkerStatus {
        self.lock().disconnect()
    }
}

#[tauri::command]
pub fn worker_defaults() -> WorkerDefaults {
    // Development builds know the repository location. Packaged apps still let
    // the owner choose an already prepared checkout if this location is absent.
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(3);
    WorkerDefaults {
        project_root: root
            .and_then(|path| canonical_project(path).ok())
            .map(|path| path.to_string_lossy().into_owned())
            .unwrap_or_default(),
    }
}

#[tauri::command]
pub fn connect_worker(
    app: AppHandle,
    state: State<'_, WorkerManager>,
    project_root: String,
    server: String,
    session_token: String,
    backend: String,
) -> WorkerStatus {
    let mut runtime = state.lock();
    runtime.refresh();
    if runtime.child.is_some() {
        return runtime.status.clone();
    }
    let plan = (|| {
        let root = canonical_project(Path::new(&project_root))?;
        let server = validate_server(&server)?;
        validate_backend(&backend)?;
        validate_session_token(&session_token)?;
        let app_data = app
            .path()
            .app_data_dir()
            .map_err(|_| "Cannot locate desktop app storage. Restart PocketGrid and try again.")?;
        let identity_dir = app_data.join("desktop-workers");
        create_identity_dir(&identity_dir)?;
        Ok::<_, &'static str>(LaunchPlan {
            identity: identity_path(&identity_dir, &server, &session_token),
            root,
            server,
            session_token,
            backend,
        })
    })();
    match plan {
        Ok(plan) => runtime.start(plan.command(), &plan.backend),
        Err(message) => runtime.fail(message),
    }
}

#[tauri::command]
pub fn worker_status(state: State<'_, WorkerManager>) -> WorkerStatus {
    let mut runtime = state.lock();
    runtime.refresh();
    runtime.status.clone()
}

#[tauri::command]
pub fn disconnect_worker(state: State<'_, WorkerManager>) -> WorkerStatus {
    state.disconnect()
}

fn canonical_project(path: &Path) -> Result<PathBuf, &'static str> {
    if path.as_os_str().is_empty() || !path.is_absolute() {
        return Err("Choose the absolute path to your prepared PocketGrid project folder.");
    }
    let root = path
        .canonicalize()
        .map_err(|_| "Project folder was not found. Choose your prepared PocketGrid checkout.")?;
    if !root.join("workers/python/worker.py").is_file() {
        return Err("This folder does not contain workers/python/worker.py. Choose the PocketGrid project folder.");
    }
    let python = root.join("workers/python/.venv/bin/python");
    if !python.is_file() {
        return Err("The local worker environment is missing. Complete the Python worker setup in README, then connect again.");
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if python
            .metadata()
            .map(|metadata| metadata.permissions().mode() & 0o111 == 0)
            .unwrap_or(true)
        {
            return Err("The local Python worker interpreter is not executable. Repair its environment and reconnect.");
        }
    }
    Ok(root)
}

fn validate_server(value: &str) -> Result<String, &'static str> {
    const INVALID: &str = "Coordinator must be an http:// or https:// origin, without credentials, a path, query, or fragment.";
    // Reject URL parser fixups such as whitespace, backslashes, or http:host.
    if !(value.starts_with("http://") || value.starts_with("https://"))
        || value
            .chars()
            .any(|character| character.is_whitespace() || character.is_control())
        || value.contains(['\\', '@'])
    {
        return Err(INVALID);
    }
    let authority = value.split_once("://").ok_or(INVALID)?.1;
    if authority.starts_with('/')
        || authority
            .split_once('/')
            .is_some_and(|(_, path)| !path.is_empty())
    {
        return Err(INVALID);
    }
    let parsed = Url::parse(value).map_err(|_| INVALID)?;
    if !matches!(parsed.scheme(), "http" | "https")
        || parsed.host_str().is_none()
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
        || parsed.path() != "/"
    {
        return Err(INVALID);
    }
    Ok(parsed.origin().ascii_serialization())
}

fn validate_backend(value: &str) -> Result<(), &'static str> {
    if matches!(value, "auto" | "cpu" | "mps" | "cuda") {
        Ok(())
    } else {
        Err("Choose Automatic, CPU, Apple GPU (MPS), or CUDA for the local worker.")
    }
}

fn validate_session_token(value: &str) -> Result<(), &'static str> {
    if value.is_empty() || value.len() > 4096 || !value.bytes().all(|byte| byte.is_ascii_graphic())
    {
        Err("Join the grid before connecting this Mac's image worker.")
    } else {
        Ok(())
    }
}

fn create_identity_dir(path: &Path) -> Result<(), &'static str> {
    std::fs::create_dir_all(path)
        .map_err(|_| "Cannot create private worker storage in PocketGrid app data.")?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
            .map_err(|_| "Cannot secure private worker storage in PocketGrid app data.")?;
    }
    Ok(())
}

fn identity_path(directory: &Path, server: &str, session_token: &str) -> PathBuf {
    let mut hasher = Sha256::new();
    hasher.update(server.as_bytes());
    hasher.update([0]);
    hasher.update(session_token.as_bytes());
    directory.join(format!("{:x}.json", hasher.finalize()))
}

struct LaunchPlan {
    root: PathBuf,
    identity: PathBuf,
    server: String,
    session_token: String,
    backend: String,
}

impl LaunchPlan {
    fn command(&self) -> Command {
        let mut command = Command::new(self.root.join("workers/python/.venv/bin/python"));
        command
            .current_dir(&self.root)
            .arg("-u")
            .arg(self.root.join("workers/python/worker.py"))
            .args(["run", "--server", &self.server, "--identity"])
            .arg(&self.identity)
            .args([
                "--device-name",
                "This Mac image worker",
                "--generate-only",
                "--connect-paused",
                "--local-only",
                "--backend",
                &self.backend,
            ])
            .env("POCKETGRID_SESSION_TOKEN", &self.session_token)
            .env("HF_HUB_OFFLINE", "1")
            .env("TRANSFORMERS_OFFLINE", "1");
        command
    }
}

#[derive(Deserialize, Debug)]
struct Ready {
    device_id: String,
    backend: String,
    model: String,
}

fn parse_ready(line: &str) -> Option<Ready> {
    if line.len() > MAX_OUTPUT_LINE {
        return None;
    }
    let value = line.strip_prefix("POCKETGRID_READY ")?;
    let ready: Ready = serde_json::from_str(value).ok()?;
    // Coordinator device IDs are UUID hex. Validate all returned strings, and
    // never forward arbitrary JSON fields or the model's diagnostic text.
    if ready.device_id.len() != 32
        || !ready.device_id.bytes().all(|byte| byte.is_ascii_hexdigit())
        || !matches!(ready.backend.as_str(), "cpu" | "mps" | "cuda")
        || ready.model.is_empty()
        || ready.model.len() > 256
        || ready.model.chars().any(char::is_control)
    {
        return None;
    }
    Some(ready)
}

enum WorkerEvent {
    Ready(Ready),
    Hint(&'static str),
}

fn diagnostic_hint(line: &str) -> Option<&'static str> {
    let lower = line.to_ascii_lowercase();
    if lower.contains("no module named") || lower.contains("modulenotfounderror") {
        Some("The worker's Python dependencies are missing. Complete worker setup in README and reconnect.")
    } else if lower.contains("mps")
        && (lower.contains("unavailable") || lower.contains("not available"))
    {
        Some("Apple GPU (MPS) is unavailable to this worker. Choose CPU or repair GPU access, then reconnect.")
    } else if lower.contains("cuda")
        && (lower.contains("unavailable") || lower.contains("not available"))
    {
        Some("CUDA is unavailable to this worker. Choose Automatic or CPU, then reconnect.")
    } else if lower.contains("localentrynotfounderror")
        || lower.contains("local_files_only")
        || lower.contains("cached snapshot")
        || lower.contains("disk cache")
        || lower.contains("offline mode")
        || lower.contains("not in the cached")
    {
        Some("The image model is not fully cached locally. Prepare the worker model using README, then reconnect. Connect never downloads models.")
    } else if lower.contains("401")
        || lower.contains("403")
        || lower.contains("unauthorized")
        || lower.contains("forbidden")
        || lower.contains("session expired")
    {
        Some("The coordinator rejected this session. Rejoin the grid, then connect the worker again.")
    } else if lower.contains("connecterror")
        || lower.contains("connection refused")
        || lower.contains("timed out")
        || lower.contains("timeout")
    {
        Some("The worker could not reach the coordinator. Check its address and connection, then reconnect.")
    } else if lower.contains("unrecognized arguments") && lower.contains("connect-paused") {
        Some("This checkout's worker is too old for desktop connection. Update the PocketGrid checkout and reconnect.")
    } else if lower.contains("loading ") && lower.contains("no job lease") {
        Some("Loading the installed image model locally. Sharing remains off until you start it.")
    } else {
        None
    }
}

fn read_output(mut output: impl Read, stdout: bool, sender: mpsc::SyncSender<WorkerEvent>) {
    let mut chunk = [0u8; 1024];
    let mut line = Vec::with_capacity(MAX_OUTPUT_LINE);
    let mut oversized = false;
    let mut ready_sent = false;
    let mut hints = HashSet::new();
    let mut emit = |line: &[u8]| {
        let line = String::from_utf8_lossy(line);
        if stdout && !ready_sent {
            if let Some(ready) = parse_ready(line.trim_end_matches('\r')) {
                let _ = sender.try_send(WorkerEvent::Ready(ready));
                ready_sent = true;
            }
        }
        if let Some(hint) = diagnostic_hint(&line) {
            // Each stream emits at most one event per fixed hint, so readiness
            // cannot be crowded out by repeated warnings in the bounded queue.
            if hints.insert(hint) {
                let _ = sender.try_send(WorkerEvent::Hint(hint));
            }
        }
    };
    loop {
        let count = match output.read(&mut chunk) {
            Ok(0) | Err(_) => break,
            Ok(count) => count,
        };
        for byte in &chunk[..count] {
            if *byte == b'\n' {
                if !oversized {
                    emit(&line);
                }
                line.clear();
                oversized = false;
            } else if !oversized {
                if line.len() == MAX_OUTPUT_LINE {
                    line.clear();
                    oversized = true;
                } else {
                    line.push(*byte);
                }
            }
        }
    }
    if !oversized && !line.is_empty() {
        emit(&line);
    }
}

struct ManagedChild {
    process: Child,
    events: mpsc::Receiver<WorkerEvent>,
    started_at: Instant,
}

impl ManagedChild {
    fn terminate(&mut self) -> bool {
        // kill may race a natural exit; wait always reaps that case as well.
        let _ = self.process.kill();
        self.process.wait().is_ok()
    }
}

impl Drop for ManagedChild {
    fn drop(&mut self) {
        self.terminate();
    }
}

#[derive(Default)]
struct WorkerRuntime {
    child: Option<ManagedChild>,
    status: WorkerStatus,
    last_hint: Option<&'static str>,
}

impl WorkerRuntime {
    fn start(&mut self, mut command: Command, backend: &str) -> WorkerStatus {
        self.refresh();
        if self.child.is_some() {
            return self.status.clone();
        }
        self.last_hint = None;
        let child = command
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();
        match child {
            Ok(mut process) => {
                let (sender, events) = mpsc::sync_channel(32);
                if let Some(stdout) = process.stdout.take() {
                    let sender = sender.clone();
                    thread::spawn(move || read_output(stdout, true, sender));
                }
                if let Some(stderr) = process.stderr.take() {
                    thread::spawn(move || read_output(stderr, false, sender));
                }
                self.child = Some(ManagedChild { process, events, started_at: Instant::now() });
                self.status = WorkerStatus {
                    phase: WorkerPhase::Starting,
                    device_id: None,
                    backend: Some(backend.into()),
                    message: "Starting the installed local image worker. Sharing stays off until you start it.".into(),
                };
                self.status.clone()
            }
            Err(_) => self.fail("Could not start the installed Python worker. Check the project folder and worker environment, then reconnect."),
        }
    }

    fn refresh(&mut self) {
        let Some(child) = self.child.as_mut() else {
            return;
        };
        for event in child.events.try_iter().take(32) {
            match event {
                WorkerEvent::Ready(ready) => {
                    self.status.phase = WorkerPhase::Connected;
                    self.status.device_id = Some(ready.device_id);
                    self.status.backend = Some(ready.backend);
                    self.status.message = "Image worker connected. Start sharing in its device controls when you are ready.".into();
                    self.last_hint = None;
                }
                WorkerEvent::Hint(hint) => {
                    if !hint.starts_with("Loading the installed") {
                        self.last_hint = Some(hint);
                    }
                    if self.status.phase == WorkerPhase::Starting {
                        self.status.message = hint.into();
                    }
                }
            }
        }
        match child.process.try_wait() {
            Ok(Some(_)) => {
                self.child = None;
                self.status.phase = WorkerPhase::Failed;
                self.status.message = self.last_hint.unwrap_or("Local image worker exited. Check the prepared worker environment and coordinator, then connect again.").into();
            }
            Err(_) => {
                self.child = None;
                self.status.phase = WorkerPhase::Failed;
                self.status.message = "Could not inspect the local worker process. It has been stopped; connect again.".into();
            }
            Ok(None)
                if self.status.phase == WorkerPhase::Starting
                    && child.started_at.elapsed() > STARTUP_TIMEOUT =>
            {
                self.child = None;
                self.status.phase = WorkerPhase::Failed;
                self.status.message = "Local worker startup timed out after five minutes and was stopped. Check its cached model and coordinator, then reconnect.".into();
            }
            Ok(None) => {}
        }
    }

    fn fail(&mut self, message: &str) -> WorkerStatus {
        self.status = WorkerStatus {
            phase: WorkerPhase::Failed,
            message: message.into(),
            ..WorkerStatus::default()
        };
        self.status.clone()
    }

    fn disconnect(&mut self) -> WorkerStatus {
        // Capture a readiness line received just before Disconnect, so the UI
        // can also pause the paired device through its existing owner API.
        self.refresh();
        if let Some(mut child) = self.child.take() {
            if !child.terminate() {
                self.child = Some(child);
                return self.fail("Could not confirm that the local worker stopped. Retry Disconnect before connecting another worker.");
            }
        }
        self.status = WorkerStatus {
            device_id: self.status.device_id.take(),
            backend: self.status.backend.take(),
            ..WorkerStatus::default()
        };
        self.last_hint = None;
        self.status.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Cursor, Write};

    const DEVICE_ID: &str = "0123456789abcdef0123456789abcdef";
    const TOKEN: &str = "private-test-session-token";

    #[test]
    fn validates_origins_without_credentials_or_url_fixups() {
        for (input, expected) in [
            ("http://127.0.0.1:8787", "http://127.0.0.1:8787"),
            ("https://example.com/", "https://example.com"),
            ("http://[::1]:8787", "http://[::1]:8787"),
        ] {
            assert_eq!(validate_server(input).unwrap(), expected);
        }
        for input in [
            "",
            "example.com",
            "file:///tmp/test",
            "http:example.com",
            "http:///example.com",
            "https://user:password@example.com",
            "https://@example.com",
            "https://example.com/path",
            "https://example.com/a/..",
            "https://example.com/%2e",
            "https://example.com?token=secret",
            "https://example.com#fragment",
            " https://example.com",
            "https://example.com\n",
            "https://example.com\\path",
            "https://example.com:invalid",
        ] {
            assert!(
                validate_server(input).is_err(),
                "accepted invalid origin: {input:?}"
            );
        }
    }

    #[test]
    fn validates_backend_and_session_without_echoing_input() {
        for backend in ["auto", "cpu", "mps", "cuda"] {
            assert!(validate_backend(backend).is_ok());
        }
        assert!(validate_backend("cpu --share").is_err());
        assert!(validate_session_token(TOKEN).is_ok());
        for token in ["", "\nsecret", "one two", "\0secret"] {
            assert!(validate_session_token(token).is_err());
        }
        assert!(validate_session_token(&"x".repeat(4097)).is_err());
    }

    #[test]
    fn identity_is_stable_private_and_scoped_to_origin_and_session() {
        let directory = Path::new("/private/app-data/desktop-workers");
        let first = identity_path(directory, "http://localhost:8787", TOKEN);
        assert_eq!(
            first,
            identity_path(directory, "http://localhost:8787", TOKEN)
        );
        assert_ne!(
            first,
            identity_path(directory, "http://localhost:8788", TOKEN)
        );
        assert_ne!(
            first,
            identity_path(directory, "http://localhost:8787", "other-session")
        );
        assert_eq!(first.parent(), Some(directory));
        assert_eq!(first.file_name().unwrap().to_string_lossy().len(), 69);
        assert!(!first.to_string_lossy().contains(TOKEN));
    }

    #[test]
    fn launch_uses_fixed_arguments_and_environment_only_for_token() {
        let plan = LaunchPlan {
            root: PathBuf::from("/tmp/PocketGrid project"),
            identity: PathBuf::from("/private/app-data/desktop-workers/hash.json"),
            server: "http://127.0.0.1:8787".into(),
            session_token: TOKEN.into(),
            backend: "mps".into(),
        };
        let command = plan.command();
        assert_eq!(
            command.get_program(),
            "/tmp/PocketGrid project/workers/python/.venv/bin/python"
        );
        assert_eq!(command.get_current_dir(), Some(plan.root.as_path()));
        let arguments: Vec<_> = command
            .get_args()
            .map(|value| value.to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            arguments,
            [
                "-u",
                "/tmp/PocketGrid project/workers/python/worker.py",
                "run",
                "--server",
                "http://127.0.0.1:8787",
                "--identity",
                "/private/app-data/desktop-workers/hash.json",
                "--device-name",
                "This Mac image worker",
                "--generate-only",
                "--connect-paused",
                "--local-only",
                "--backend",
                "mps",
            ]
        );
        assert!(!arguments
            .iter()
            .any(|value| value.contains(TOKEN) || value == "--share"));
        let token = command
            .get_envs()
            .find(|(key, _)| *key == "POCKETGRID_SESSION_TOKEN")
            .unwrap()
            .1;
        assert_eq!(token, Some(std::ffi::OsStr::new(TOKEN)));
    }

    #[test]
    fn project_requires_preinstalled_worker_and_executable_python() {
        let directory =
            std::env::temp_dir().join(format!("pocketgrid-project-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(directory.join("workers/python/.venv/bin")).unwrap();
        assert!(canonical_project(&directory).is_err());
        std::fs::write(directory.join("workers/python/worker.py"), "# fixture").unwrap();
        assert!(canonical_project(&directory).is_err());
        let python = directory.join("workers/python/.venv/bin/python");
        std::fs::write(&python, "fixture").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert!(canonical_project(&directory).is_err());
            std::fs::set_permissions(&python, std::fs::Permissions::from_mode(0o700)).unwrap();
        }
        assert_eq!(
            canonical_project(&directory).unwrap(),
            directory.canonicalize().unwrap()
        );
        assert!(canonical_project(Path::new("relative/project")).is_err());
        std::fs::remove_dir_all(directory).unwrap();
    }

    fn ready_line() -> String {
        format!("POCKETGRID_READY {{\"device_id\":\"{DEVICE_ID}\",\"backend\":\"cpu\",\"model\":\"segmind/tiny-sd\"}}")
    }

    #[test]
    fn readiness_requires_structured_valid_device_and_backend() {
        let ready = parse_ready(&ready_line()).unwrap();
        assert_eq!(ready.device_id, DEVICE_ID);
        assert_eq!(ready.backend, "cpu");
        assert!(parse_ready("Device abc connected").is_none());
        assert!(parse_ready("POCKETGRID_READY malformed").is_none());
        assert!(parse_ready(&ready_line().replace(DEVICE_ID, TOKEN)).is_none());
        assert!(parse_ready(&ready_line().replace("cpu", "auto")).is_none());
        assert!(parse_ready(&ready_line().replace("tiny-sd", &"x".repeat(4096))).is_none());
    }

    #[test]
    fn output_is_bounded_sanitized_and_readiness_is_stdout_only() {
        let (sender, receiver) = mpsc::sync_channel(32);
        let logs = format!(
            "{}\nModuleNotFoundError: No module named '{TOKEN}'\n{}\n",
            "x".repeat(20_000),
            ready_line()
        );
        read_output(Cursor::new(logs), true, sender);
        let events: Vec<_> = receiver.try_iter().collect();
        assert_eq!(events.len(), 2);
        assert!(matches!(&events[0], WorkerEvent::Hint(message) if !message.contains(TOKEN)));
        assert!(matches!(&events[1], WorkerEvent::Ready(ready) if ready.device_id == DEVICE_ID));
        let (sender, receiver) = mpsc::sync_channel(32);
        read_output(Cursor::new(ready_line()), false, sender);
        assert!(receiver.try_recv().is_err());
        assert_eq!(diagnostic_hint(&format!("401 Unauthorized {TOKEN}")).unwrap(), "The coordinator rejected this session. Rejoin the grid, then connect the worker again.");
    }

    fn fake_child(mode: &str) -> Command {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args([
                "--ignored",
                "--exact",
                "worker::tests::child_fixture",
                "--nocapture",
            ])
            .env("POCKETGRID_CHILD_TEST_MODE", mode);
        command
    }

    #[test]
    #[ignore = "invoked only as an isolated test subprocess"]
    fn child_fixture() {
        match std::env::var("POCKETGRID_CHILD_TEST_MODE").as_deref() {
            Ok("ready") => {
                println!("{}", ready_line());
                std::io::stdout().flush().unwrap();
                thread::sleep(Duration::from_secs(60));
            }
            Ok("exit") => std::process::exit(9),
            _ => panic!("fixture mode required"),
        }
    }

    fn await_phase(runtime: &mut WorkerRuntime, phase: WorkerPhase) {
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            runtime.refresh();
            if runtime.status.phase == phase {
                return;
            }
            assert!(
                Instant::now() < deadline,
                "worker never reached {phase:?}: {:?}",
                runtime.status
            );
            thread::sleep(Duration::from_millis(10));
        }
    }

    #[test]
    fn one_child_at_a_time_and_disconnect_retains_device_but_reaps_process() {
        let mut runtime = WorkerRuntime::default();
        assert_eq!(
            runtime.start(fake_child("ready"), "cpu").phase,
            WorkerPhase::Starting
        );
        let pid = runtime.child.as_ref().unwrap().process.id();
        runtime.start(fake_child("ready"), "cpu");
        assert_eq!(runtime.child.as_ref().unwrap().process.id(), pid);
        await_phase(&mut runtime, WorkerPhase::Connected);
        assert_eq!(runtime.status.device_id.as_deref(), Some(DEVICE_ID));
        assert_eq!(runtime.disconnect().phase, WorkerPhase::Stopped);
        assert!(runtime.child.is_none());
        assert_eq!(runtime.status.device_id.as_deref(), Some(DEVICE_ID));
        assert_eq!(runtime.disconnect().phase, WorkerPhase::Stopped);
        #[cfg(unix)]
        assert!(!Command::new("/bin/kill")
            .args(["-0", &pid.to_string()])
            .stderr(Stdio::null())
            .status()
            .unwrap()
            .success());
    }

    #[test]
    fn unexpected_exit_and_spawn_failure_are_retryable() {
        let mut runtime = WorkerRuntime::default();
        assert_eq!(
            runtime.start(Command::new("/no/such/python"), "cpu").phase,
            WorkerPhase::Failed
        );
        assert!(runtime.child.is_none());
        assert_eq!(
            runtime.start(fake_child("exit"), "cpu").phase,
            WorkerPhase::Starting
        );
        await_phase(&mut runtime, WorkerPhase::Failed);
        assert!(runtime.child.is_none());
        assert_eq!(
            runtime.start(fake_child("ready"), "cpu").phase,
            WorkerPhase::Starting
        );
        runtime.disconnect();
    }

    #[test]
    fn startup_timeout_terminates_and_drop_reaps_child() {
        let mut runtime = WorkerRuntime::default();
        runtime.start(fake_child("ready"), "cpu");
        let mut child = runtime.child.take().unwrap();
        let pid = child.process.id();
        child.started_at = Instant::now() - STARTUP_TIMEOUT - Duration::from_secs(1);
        // Use an empty event receiver so this fixture deterministically stays starting.
        child.events = mpsc::sync_channel(1).1;
        runtime.child = Some(child);
        runtime.refresh();
        assert_eq!(runtime.status.phase, WorkerPhase::Failed);
        assert!(runtime.status.message.contains("timed out"));
        assert!(runtime.child.is_none());
        #[cfg(unix)]
        assert!(!Command::new("/bin/kill")
            .args(["-0", &pid.to_string()])
            .stderr(Stdio::null())
            .status()
            .unwrap()
            .success());
        runtime.start(fake_child("ready"), "cpu");
        let pid = runtime.child.as_ref().unwrap().process.id();
        drop(runtime);
        #[cfg(unix)]
        assert!(!Command::new("/bin/kill")
            .args(["-0", &pid.to_string()])
            .stderr(Stdio::null())
            .status()
            .unwrap()
            .success());
    }

    #[test]
    fn status_serializes_camel_case_and_omits_absent_fields() {
        let status = WorkerStatus {
            phase: WorkerPhase::Connected,
            device_id: Some(DEVICE_ID.into()),
            backend: Some("cpu".into()),
            message: "Connected".into(),
        };
        let value = serde_json::to_value(status).unwrap();
        assert_eq!(value["phase"], "connected");
        assert_eq!(value["deviceId"], DEVICE_ID);
        assert!(value.get("device_id").is_none());
        let value = serde_json::to_value(WorkerStatus::default()).unwrap();
        assert_eq!(value["phase"], "stopped");
        assert!(value.get("deviceId").is_none());
    }
}
