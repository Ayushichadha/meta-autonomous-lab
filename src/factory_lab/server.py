"""Local development dashboard. Only allowlisted assets and bounded actions are exposed."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
from pathlib import Path
from threading import Lock, Thread
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import dotenv_values
from pydantic import Field

from .domain import Incident, Model, Plan, Scenario, Snapshot
from .experiments import run_comparison
from .scenarios import load_demo


class RunRequest(Model):
    outage_at: int = Field(default=25, ge=1, le=200)
    repair_at: int = Field(default=115, ge=2, le=400)
    machine: str = "CNC-A"
    provider: str = "meta"


class EpisodeRequest(Model):
    policy: Literal["preserve", "always_replan", "fixed_interval", "solver_selection", "meta"] = "solver_selection"
    provider: Literal["meta", "baseten"] = "meta"


def local_budget_status() -> dict:
    from .budget import BudgetLedger
    ledger = BudgetLedger()
    with ledger.locked() as (_, records):
        latest = {r["request_id"]: r for r in records}
    return {"limit_usd": 1.0, "reserved_or_estimated_usd": sum(r["charged_usd"] for r in latest.values()),
            "note": "Local estimate/reservations, not the provider account balance."}


def read_recorded(paths: list[str]) -> dict:
    for name in paths:
        path = Path(name)
        if path.is_file():
            return json.loads(path.read_text())
    raise FileNotFoundError("No recorded artifact is available yet")


def provider_status() -> dict:
    local = dotenv_values(".env")
    def value(key):
        return os.getenv(key) or local.get(key)
    return {
        "baseten": {"configured": bool(value("BASETEN_API_KEY")),
                    "model": value("BASETEN_MODEL") or "meta-models/muse-spark-open-1026"},
        "meta": {"configured": bool(value("META_API_KEY") or value("MODEL_API_KEY")),
                 "model": value("META_MODEL") or "muse-spark-1.3"},
    }


def run_dashboard(port: int = 8765) -> None:
    busy = Lock()
    jobs_lock = Lock()
    jobs = {}
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    assets = {"/": ("console.html", "text/html"), "/single": ("index.html", "text/html"),
              "/app.css": ("app.css", "text/css"), "/app.js": ("app.js", "text/javascript"),
              "/console.css": ("console.css", "text/css"), "/console.js": ("console.js", "text/javascript")}

    def episode_worker(job_id, request):
        from .episode import EpisodeConfig, demo_events, live_supervisor, run_episode
        def progress(item):
            with jobs_lock:
                jobs[job_id]["progress"].append(item)
                jobs[job_id]["progress"] = jobs[job_id]["progress"][-100:]
        def frame_ready(frame):
            with jobs_lock:
                jobs[job_id]["frames"].append(frame)
            progress({"stage": "observation_recorded", "time": frame["time"]})
        try:
            config = EpisodeConfig()
            callback = live_supervisor(request.provider, solve_seconds=config.solve_seconds,
                on_progress=progress) if request.policy == "meta" else None
            result = run_episode(load_demo(), demo_events(), policy=request.policy, config=config,
                supervisor=callback, on_frame=frame_ready)
            result["run_id"] = job_id
            path = Path("runs") / (job_id + "-episode.json")
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(result, indent=2) + "\n")
            with jobs_lock:
                jobs[job_id].update(status="completed", result=result)
        except Exception as error:
            with jobs_lock:
                jobs[job_id].update(status="failed", error=str(error).split("\n")[0][:250])
        finally:
            busy.release()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Keep request material and provider data out of routine logs.
            pass

        def send(self, status, content, content_type="application/json"):
            body = json.dumps(content).encode() if content_type == "application/json" else content
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def local_request(self):
            if self.headers.get("Host") not in allowed_hosts:
                self.send(403, {"error": "Local dashboard requests only"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{host}" for host in allowed_hosts}:
                self.send(403, {"error": "Cross-origin request rejected"})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            path = urlsplit(self.path).path
            if path == "/api/status":
                self.send(200, {"providers": provider_status(), "synthetic": True, "budget": local_budget_status()})
            elif path == "/api/recorded-episode":
                try:
                    result = read_recorded(["results/demo/meta-sequential-demo.json", "runs/meta-sequential-demo.json"])
                    self.send(200, {"mode": "recorded", "episode": result})
                except FileNotFoundError:
                    self.send(404, {"error": "No recorded Meta episode is available. Execute a conventional episode to explore the twin without spending credits."})
            elif path == "/api/evaluation":
                try:
                    self.send(200, read_recorded(["results/evaluation-v2/summary.json", "runs/evaluation-v2/summary.json",
                                                "results/evaluation-v1/summary.json", "runs/evaluation-v1/summary.json"]))
                except FileNotFoundError:
                    self.send(404, {"error": "No completed evaluation summary is available yet."})
            elif path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                with jobs_lock:
                    job = jobs.get(job_id)
                    snapshot = {**job, "progress": list(job["progress"]), "frames": list(job["frames"])} if job else None
                self.send(200 if snapshot else 404, snapshot or {"error": "Unknown execution job"})
            elif path in assets:
                name, content_type = assets[path]
                self.send(200, files("factory_lab").joinpath("web", name).read_bytes(), content_type)
            else:
                self.send(404, {"error": "Not found"})

        def do_POST(self):
            if not self.local_request():
                return
            path = urlsplit(self.path).path
            if path not in {"/api/compare", "/api/agent", "/api/episode"}:
                self.send(404, {"error": "Not found"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send(415, {"error": "Use application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 8192:
                    raise ValueError("Request must be between 1 and 8192 bytes")
                raw = self.rfile.read(length)
                request = EpisodeRequest.model_validate_json(raw) if path == "/api/episode" else RunRequest.model_validate_json(raw)
                if isinstance(request, RunRequest) and request.machine not in load_demo().machines:
                    raise ValueError("Unknown machine")
                if request.provider not in {"baseten", "meta"}:
                    raise ValueError("Unknown provider")
                if isinstance(request, RunRequest) and request.repair_at <= request.outage_at:
                    raise ValueError("Repair time must follow outage time")
            except ValueError:
                self.send(400, {"error": "Check machine, provider, and times. Repair must follow the outage; use whole minutes."})
                return
            if not busy.acquire(blocking=False):
                self.send(409, {"error": "An experiment is already running. Wait for it to finish."})
                return
            if path == "/api/episode":
                job_id = uuid4().hex[:16]
                with jobs_lock:
                    for old in list(jobs):
                        if len(jobs) < 8:
                            break
                        if jobs[old]["status"] != "running":
                            del jobs[old]
                    jobs[job_id] = {"job_id": job_id, "status": "running", "progress": [],
                                    "frames": [], "scenario": load_demo().model_dump(), "policy": request.policy}
                Thread(target=episode_worker, args=(job_id, request), daemon=True).start()
                self.send(202, {"job_id": job_id, "status": "running"})
                return
            try:
                report = run_comparison(load_demo(), outage_at=request.outage_at,
                    repair_at=request.repair_at, machine=request.machine, time_limit=1.0)
                if path == "/api/agent":
                    from .agent import supervise
                    from .provider import ModelClient
                    report["agent"] = supervise(ModelClient(request.provider),
                        Scenario.model_validate(report["scenario"]), Snapshot.model_validate(report["observation"]),
                        Plan.model_validate(report["original_plan"]), Incident.model_validate(report["incident"]), time_limit=1.0)
                report["run_id"] = uuid4().hex[:12]
                destination = Path("runs") / (report["run_id"] + ".json")
                destination.parent.mkdir(exist_ok=True)
                destination.write_text(json.dumps(report, indent=2) + "\n")
                self.send(200, report)
            except (ValueError, RuntimeError) as exc:
                self.send(422, {"error": str(exc).split("\n")[0][:300]})
            except Exception:
                self.send(500, {"error": "Experiment failed unexpectedly. No recovery plan was applied."})
            finally:
                busy.release()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Factory Recovery Lab: http://127.0.0.1:{port}", flush=True)
    print("Local synthetic simulator. The Meta agent button uses API credits.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
