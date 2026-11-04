"""Local development dashboard. Only allowlisted assets and bounded actions are exposed."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import hashlib
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


class NoteRequest(Model):
    note: str = Field(min_length=1, max_length=2000)
    source_id: str = Field(default="recorded", pattern=r"^(recorded|recorded-note|[a-f0-9]{16})$")
    frame_index: int = Field(ge=0, le=2000)
    provider: Literal["meta"] = "meta"


class ImageRequest(Model):
    image: str = Field(min_length=1, max_length=700000)
    provider: Literal["meta"] = "meta"


class NoteBranchRequest(Model):
    interpretation_id: str = Field(pattern=r"^[a-f0-9]{16}$")
    policy: Literal["solver_selection", "meta"] = "solver_selection"
    provider: Literal["meta"] = "meta"


def local_budget_status() -> dict:
    from .budget import BudgetLedger
    ledger = BudgetLedger()
    if os.getenv("FACTORY_CLOUD_JOBS"):
        import modal
        try:
            data = b"".join(modal.Volume.from_name("factory-recovery-state").read_file("/runs/meta-usage.jsonl"))
            latest = {r["request_id"]:r for r in map(json.loads,data.splitlines())}
            return {"limit_usd":1.0,"reserved_or_estimated_usd":sum(r["charged_usd"] for r in latest.values())}
        except Exception:
            return {"limit_usd":1.0,"reserved_or_estimated_usd":1.0,"note":"Usage unavailable; do not start inference."}
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
        "meta": {"configured": bool(value("META_API_KEY") or value("MODEL_API_KEY") or os.getenv("FACTORY_CLOUD_JOBS")),
                 "model": value("META_MODEL") or "muse-spark-1.3"},
    }


def run_dashboard(port: int = 8765, *, bind: str = "127.0.0.1", public_host: str | None = None) -> None:
    cloud = bool(os.getenv("FACTORY_CLOUD_JOBS"))
    busy = Lock()
    jobs_lock = Lock()
    jobs = {}
    note_records = {}
    allowed_hosts = {public_host} if public_host else {f"127.0.0.1:{port}", f"localhost:{port}"}
    assets = {"/": ("console.html", "text/html"), "/single": ("index.html", "text/html"),
              "/app.css": ("app.css", "text/css"), "/app.js": ("app.js", "text/javascript"),
              "/console.css": ("console.css", "text/css"), "/console.js": ("console.js", "text/javascript")}

    def source_episode(source_id):
        if source_id == "recorded":
            return read_recorded(["results/demo/meta-sequential-demo.json", "runs/meta-sequential-demo.json"])
        if source_id == "recorded-note":
            return read_recorded(["results/notes/verified-note-workflow.json"])["branch"]
        if cloud:
            from .cloud import get
            source = get(source_id)
            if source and source["status"] == "completed" and "frames" in source.get("result", {}):
                return source["result"]
        with jobs_lock:
            source = jobs.get(source_id)
            if not source or source["status"] != "completed":
                raise ValueError("The source execution is no longer available; load the recorded run again")
            return source["result"]

    def branch_worker(job_id, request, record):
        from .branching import run_note_branch
        def progress(item):
            with jobs_lock:
                jobs[job_id]["progress"].append(item)
                jobs[job_id]["progress"] = jobs[job_id]["progress"][-100:]
        def frame_ready(frame):
            with jobs_lock:
                jobs[job_id]["frames"].append(frame)
            progress({"stage": "branch_observation_recorded", "time": frame["time"]})
        try:
            result = run_note_branch(record["source"], record["frame_index"], record["interpretation"],
                                     policy=request.policy, provider=request.provider,
                                     on_frame=frame_ready, on_progress=progress)
            result["run_id"] = job_id
            destination = Path("runs") / (job_id + "-note-branch.json")
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(json.dumps(result, indent=2) + "\n")
            destination.chmod(0o600)
            with jobs_lock:
                jobs[job_id].update(status="completed", result=result)
        except Exception as error:
            with jobs_lock:
                jobs[job_id].update(status="failed", error=str(error).split("\n")[0][:250])
        finally:
            busy.release()

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
            if origin and origin not in {f"{scheme}://{host}" for host in allowed_hosts for scheme in (["https"] if public_host else ["http"])}:
                self.send(403, {"error": "Cross-origin request rejected"})
                return False
            return True

        def do_GET(self):
            if not self.local_request():
                return
            path = urlsplit(self.path).path
            if path == "/api/status":
                self.send(200, {"providers": provider_status(), "synthetic": True, "capabilities":{"maintenance_notes":True,"vision":True}, "budget": local_budget_status()})
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
            elif path == "/api/recorded-note":
                try:
                    self.send(200, read_recorded(["results/notes/verified-note-workflow.json"]))
                except FileNotFoundError:
                    self.send(404, {"error": "No verified recorded note workflow is available yet."})
            elif path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                if cloud:
                    from .cloud import get
                    snapshot = get(job_id)
                    self.send(200 if snapshot else 404, snapshot or {"error":"Unknown execution job"})
                    return
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
            if path not in {"/api/compare", "/api/agent", "/api/episode", "/api/interpret-note", "/api/note-branch", "/api/interpret-image"}:
                self.send(404, {"error": "Not found"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send(415, {"error": "Use application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= (710000 if path == "/api/interpret-image" else 8192):
                    raise ValueError("Request exceeds the allowed size")
                raw = self.rfile.read(length)
                schema = {"/api/episode": EpisodeRequest, "/api/interpret-note": NoteRequest,
                          "/api/note-branch": NoteBranchRequest, "/api/interpret-image": ImageRequest}.get(path, RunRequest)
                request = schema.model_validate_json(raw)
                if isinstance(request, RunRequest) and request.machine not in load_demo().machines:
                    raise ValueError("Unknown machine")
                if request.provider not in {"baseten", "meta"}:
                    raise ValueError("Unknown provider")
                if isinstance(request, RunRequest) and request.repair_at <= request.outage_at:
                    raise ValueError("Repair time must follow outage time")
            except ValueError:
                self.send(400, {"error": "Invalid or oversized request. Check the image, note, observation, or event times."})
                return
            if path == "/api/interpret-image":
                try:
                    from .vision import validate_image, interpret_image
                    validate_image(request.image)
                    if cloud:
                        from .cloud import start
                        job_id=start("image",{"image":request.image,"scenario":load_demo().model_dump(),"policy":"meta"})
                        self.send(202,{"job_id":job_id})
                    else:
                        if not busy.acquire(blocking=False):
                            self.send(409,{"error":"An experiment is already running."})
                            return
                        try:
                            from .provider import ModelClient
                            self.send(200,interpret_image(ModelClient('meta'),request.image))
                        finally:
                            busy.release()
                except (ValueError,RuntimeError) as error:
                    self.send(422,{"error":str(error).split("\n")[0][:250]})
                except Exception:
                    self.send(503,{"error":"Image analysis unavailable. No update was applied; no automatic retry."})
                return
            if cloud and path in {"/api/interpret-note", "/api/note-branch"}:
                try:
                    from .cloud import start, context
                    if path == "/api/interpret-note":
                        source=source_episode(request.source_id)
                        from .branching import branch_context
                        branch_context(source,request.frame_index)
                        payload={"source":source,"frame_index":request.frame_index,"note":request.note,
                                 "scenario":source["scenario"],"policy":"meta"}
                        job_id=start("note",payload)
                    else:
                        stored=context(request.interpretation_id)
                        record=stored.get("context") if stored and stored.get("status")=="completed" else None
                        if not record or record["interpretation"]["status"]!="validated" or not record["interpretation"]["events"]:
                            raise ValueError("Validate a state-changing note first. No update applied.")
                        job_id=start("branch",{"record":record,"scenario":record["source"]["scenario"],"policy":request.policy})
                    self.send(202,{"job_id":job_id})
                except (ValueError,RuntimeError) as error:
                    self.send(422,{"error":str(error).split("\n")[0][:250]})
                except Exception:
                    self.send(503,{"error":"Cloud dispatch unavailable. No automatic inference retry."})
                return
            if cloud and path == "/api/episode":
                from .cloud import start
                try:
                    job_id = start("episode", {"policy":request.policy,"scenario":load_demo().model_dump()})
                    self.send(202,{"job_id":job_id,"status":"running"})
                except ValueError as error:
                    self.send(409,{"error":str(error)})
                except Exception:
                    self.send(503,{"error":"Cloud job dispatch is unavailable; no inference retry was made."})
                return
            if cloud and path == "/api/agent":
                self.send(422,{"error":"Hosted live inference currently supports Meta episodes. Use the recorded note workflow or run note interpretation locally."})
                return
            if not busy.acquire(blocking=False):
                self.send(409, {"error": "An experiment is already running. Wait for it to finish."})
                return
            if path == "/api/interpret-note":
                try:
                    from .branching import branch_context
                    from .notes import interpret_note
                    from .provider import ModelClient
                    source = source_episode(request.source_id)
                    scenario, state, _ = branch_context(source, request.frame_index)
                    model = os.getenv("META_MODEL") or dotenv_values(".env").get("META_MODEL") or "muse-spark-1.3"
                    fingerprint = hashlib.sha256(json.dumps({"schema_version": 1, "note": request.note,
                        "state": state.model_dump(), "scenario": scenario.model_dump(), "model": model}, sort_keys=True).encode()).hexdigest()
                    cache = Path("runs/notes") / (fingerprint + ".json")
                    if cache.exists():
                        interpretation = json.loads(cache.read_text())
                        cached = True
                    else:
                        interpretation = interpret_note(ModelClient("meta"), request.note, scenario, state)
                        cache.parent.mkdir(parents=True, exist_ok=True)
                        cache.write_text(json.dumps(interpretation, indent=2) + "\n")
                        cache.chmod(0o600)
                        cached = False
                    interpretation_id = uuid4().hex[:16]
                    with jobs_lock:
                        if len(note_records) >= 32:
                            del note_records[next(iter(note_records))]
                        note_records[interpretation_id] = {"source": source, "frame_index": request.frame_index,
                                                          "interpretation": interpretation}
                    self.send(200, {"interpretation_id": interpretation_id, "interpretation": interpretation,
                                    "cache_hit": cached, "new_request_cost_usd": 0.0 if cached else interpretation.get("estimated_cost_usd")})
                except (ValueError, RuntimeError, FileNotFoundError) as error:
                    self.send(422, {"error": str(error).split("\n")[0][:250]})
                finally:
                    busy.release()
                return
            if path == "/api/note-branch":
                with jobs_lock:
                    record = note_records.get(request.interpretation_id)
                if not record or record["interpretation"]["status"] != "validated" or not record["interpretation"]["events"]:
                    busy.release()
                    self.send(422, {"error": "Interpret a fully validated state-changing note first. Clarifications and notices do not change the twin."})
                    return
                job_id = uuid4().hex[:16]
                with jobs_lock:
                    for old in list(jobs):
                        if len(jobs) < 8:
                            break
                        if jobs[old]["status"] != "running":
                            del jobs[old]
                    jobs[job_id] = {"job_id": job_id, "status": "running", "progress": [],
                                   "frames": list(record["source"]["frames"][:record["frame_index"]]),
                                   "scenario": record["source"]["scenario"], "policy": request.policy}
                Thread(target=branch_worker, args=(job_id, request, record), daemon=True).start()
                self.send(202, {"job_id": job_id, "status": "running"})
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

    server = ThreadingHTTPServer((bind, port), Handler)
    print(f"Factory Recovery Lab: http://127.0.0.1:{port}", flush=True)
    print("Local synthetic simulator. The Meta agent button uses API credits.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
