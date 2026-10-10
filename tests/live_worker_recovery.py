"""Real-image recovery test in an isolated, temporary development grid.

Prerequisites: coordinator dependencies in .venv, worker dependencies in
workers/python/.venv, and `worker.py prepare` already completed. Starts its own
coordinator and two logical generation workers on this host. Never reads existing
identity files or changes the running demo grid. All children are stopped on exit.
"""
from __future__ import annotations
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
WORKERS = ROOT / "workers/python"
spec = importlib.util.spec_from_file_location("pocketgrid_worker", WORKERS / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def wait_for(check, timeout=180, processes=()):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"Test subprocess {process.pid} exited with {process.returncode}")
        value = check()
        if value:
            return value
        time.sleep(0.25)
    raise TimeoutError("Live worker check timed out")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    executable = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    parser.add_argument("--coordinator-python", default=str(ROOT / ".venv" / executable))
    parser.add_argument("--worker-python", default=str(WORKERS / ".venv" / executable))
    parser.add_argument("--output-dir", type=Path, default=WORKERS / ".cache/isolated-recovery")
    parser.add_argument("--timeout", type=int, default=240, help="Maximum seconds per generation phase")
    args = parser.parse_args()
    for path in (args.coordinator_python, args.worker_python):
        if not Path(path).exists():
            parser.error(f"Python environment missing: {path}; follow repository setup first")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    server = f"http://127.0.0.1:{port}"
    processes, logs = [], []
    client = httpx.Client(base_url=server, timeout=20)
    with tempfile.TemporaryDirectory(prefix="pocketgrid-recovery-") as temporary:
        temporary = Path(temporary)
        def spawn(command, environment, name):
            log = (args.output_dir / f"{name}.log").open("w")
            logs.append(log)
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            return process

        join_code = secrets.token_urlsafe(18)
        environment = dict(os.environ, POCKETGRID_DATA=str(temporary / "data"), POCKETGRID_AGENT_MODE="manual", POCKETGRID_JOIN_CODE=join_code,
                           POCKETGRID_WEB_DIR=str(temporary / "no-web-build-needed"))
        coordinator = spawn([args.coordinator_python, "-m", "uvicorn", "services.coordinator.app:app", "--host", "127.0.0.1", "--port", str(port)], environment, "coordinator")
        evidence = {"physical_hosts": 1, "description": "Real local diffusion on two isolated logical processes; abrupt death and lease recovery",
                    "termination": "SIGKILL" if os.name != "nt" else "TerminateProcess"}
        try:
            def healthy():
                try:
                    return client.get("/api/health").status_code == 200
                except httpx.TransportError:
                    return False
            wait_for(healthy, timeout=30, processes=(coordinator,))
            response = client.post("/api/sessions", json={"name": "Isolated recovery test", "join_code": join_code})
            response.raise_for_status()
            owner_token = response.json()["token"]
            client.headers["Authorization"] = f"Bearer {owner_token}"

            def api(method, path, **kwargs):
                r = client.request(method, "/api" + path, **kwargs)
                r.raise_for_status()
                return r.json()

            def sharing(device_id, enabled):
                return api("PATCH", f"/devices/{device_id}", json={"enabled": enabled})

            worker_environment = dict(environment, POCKETGRID_SESSION_TOKEN=owner_token)
            identities = [temporary / "worker-a.json", temporary / "worker-b.json"]
            children = []
            for index, identity in enumerate(identities):
                command = [args.worker_python, str(WORKERS / "worker.py"), "run", "--local-only", "--generate-only", "--server", server,
                           "--device-name", f"Isolated generation {'A' if index == 0 else 'B'}", "--identity", str(identity)]
                if index == 0:
                    command.append("--share")
                children.append(spawn(command, worker_environment, f"worker-{'a' if index == 0 else 'b'}"))
            wait_for(lambda: all(path.exists() for path in identities), timeout=60, processes=children)
            first, second = [json.loads(path.read_text()) for path in identities]
            print("Isolated coordinator and both local model workers ready", flush=True)

            def submit(prompt):
                return api("POST", "/jobs", json={"prompt": prompt, "count": 1, "width": 512, "height": 512, "steps": 30,
                           "budget": 10, "request_id": str(uuid.uuid4()), "use_agent": False})

            job = submit("A cute orange cat riding a tiny blue bicycle, side view, cartoon illustration")
            job_id = job["id"]
            def generation(job_id=job_id):
                return next(t for t in api("GET", f"/jobs/{job_id}")["tasks"] if t["kind"] == "image_generate")

            active = wait_for(lambda: (t if (t := generation())["status"] == "running" and t.get("device_id") == first["device_id"]
                                      and t.get("progress", 0) > 0.01 else None), timeout=args.timeout, processes=children)
            evidence.update(job_id=job_id, task_id=active["id"], first_device=active["device_id"], first_attempt=active["attempts"], progress_when_killed=active["progress"])
            children[0].kill()  # Only the exact child created by this script.
            children[0].wait(timeout=10)
            killed_at = time.monotonic()
            sharing(second["device_id"], True)
            reassigned = wait_for(lambda: (t if (t := generation())["attempts"] >= 2 and t.get("device_id") == second["device_id"] else None),
                                  timeout=45, processes=(coordinator, children[1]))
            evidence.update(reassigned_after_seconds=round(time.monotonic() - killed_at, 2), second_device=reassigned["device_id"], second_attempt=reassigned["attempts"], same_task=reassigned["id"] == active["id"])
            print(f"Same task reclaimed on attempt {reassigned['attempts']} after {evidence['reassigned_after_seconds']} seconds", flush=True)
            wait_for(lambda: generation()["status"] == "completed", timeout=args.timeout, processes=(coordinator, children[1]))
            evidence["generation_completed"] = True

            exporter = api("POST", "/devices", json={"name": "Isolated CPU image finalizer", "kind": "python", "capabilities": ["image_finalize"],
                           "limits": {"cpu_threads": 1, "max_pixels": 262144, "session_minutes": 5}})
            sharing(exporter["device"]["id"], True)
            with httpx.Client(base_url=server, headers={"Authorization": f"Bearer {exporter['token']}"}, timeout=10) as export:
                r = export.post(f"/api/devices/{exporter['device']['id']}/claim", json={})
                r.raise_for_status()
                task = r.json()["task"]
                assert task and task["job_id"] == job_id and task["kind"] == "image_finalize"
                png = export.get(task["source_url"])
                png.raise_for_status()
                output = worker.finalize_image(png.content)
                r = export.post(f"/api/tasks/{task['id']}/complete", json={"lease_id": task["lease_id"], "png_base64": base64.b64encode(output).decode(), "metrics": {"backend": "cpu", "model": "Pillow"}})
                r.raise_for_status()
            completed = api("GET", f"/jobs/{job_id}")
            assert completed["status"] == "completed"
            evidence["receipt"] = completed["receipt"]
            image_entry = next(x for x in completed["images"] if x["stage"] == "image_finalize")
            artifact = client.get(image_entry["url"])
            artifact.raise_for_status()
            (args.output_dir / "recovery-cat.png").write_bytes(artifact.content)
            sharing(exporter["device"]["id"], False)
            crashed_device = next(d for d in api("GET", "/state")["devices"] if d["id"] == first["device_id"])
            evidence["crashed_device_earned"] = crashed_device["earned"]
            assert crashed_device["earned"] == 0
            sharing(first["device_id"], False)

            paused_job = submit("A cartoon cat on a bicycle")
            wait_for(lambda: (t if (t := generation(paused_job["id"]))["status"] == "running" and t.get("progress", 0) > 0.01 else None),
                     timeout=args.timeout, processes=(coordinator, children[1]))
            sharing(second["device_id"], False)
            wait_for(lambda: "WorkCancelled" in (args.output_dir / "worker-b.log").read_text(), timeout=20, processes=(children[1],))
            cancelled = api("POST", f"/jobs/{paused_job['id']}/cancel", json={})
            evidence["pause"] = {"job_id": cancelled["id"], "status": cancelled["status"], "spent": cancelled["spent"], "refunded": cancelled["refunded"],
                                 "images": len(cancelled["images"]), "worker_logged_cancel": True}
            assert evidence["pause"]["spent"] == 0 and evidence["pause"]["refunded"] == 10 and evidence["pause"]["images"] == 0
            assert evidence["same_task"] and evidence["receipt"]["total_charged"] == 8
            evidence["success"] = True
            (args.output_dir / "live-recovery-evidence.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence, indent=2))
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            client.close()
            for log in logs:
                log.close()


if __name__ == "__main__":
    main()
