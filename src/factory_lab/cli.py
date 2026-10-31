import argparse
import json
from pathlib import Path
import sys

from .experiments import prepare, run_comparison
from .scenarios import development_scenario, load_demo


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def print_comparison(report: dict) -> None:
    print("FACTORY RECOVERY LAB | synthetic development simulation | no AI used")
    print("Policy         Weighted late min   On-time orders   Reroutes   Shift min")
    for candidate in report["candidates"]:
        m = candidate["nominal_metrics"]
        print(f"{candidate['policy']:<14} {m['weighted_tardiness_minutes']:>17}   "
              f"{m['on_time_orders']:>2}/{m['total_orders']:<12} {m['rerouted_operations']:>8}   "
              f"{m['queued_start_shift_minutes']:>9}")
    print("These are forecasts under the nominal repair estimate, not a held-out benchmark.")


def main():
    parser = argparse.ArgumentParser(description="Factory Recovery Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run the offline simulator and three conventional recovery candidates")
    demo.add_argument("--output", type=Path, default=Path("runs/demo.json"))
    demo.add_argument("--solve-seconds", type=float, default=3.0)
    demo.add_argument("--repair-at", type=int, default=115)
    smoke = commands.add_parser("smoke", help="Check provider catalog and real tool calling (uses API credits)")
    smoke.add_argument("--provider", choices=["baseten", "meta"], default="baseten")
    agent = commands.add_parser("agent", help="Run the real model supervisor on the demo outage (uses API credits)")
    agent.add_argument("--provider", choices=["baseten", "meta"], default="baseten")
    agent.add_argument("--output", type=Path, default=Path("runs/agent.json"))
    agent.add_argument("--solve-seconds", type=float, default=3.0)
    batch = commands.add_parser("development-batch", help="Run seeded development cases; not held-out evaluation")
    batch.add_argument("--count", type=int, default=5)
    batch.add_argument("--solve-seconds", type=float, default=1.0)
    batch.add_argument("--output", type=Path, default=Path("runs/development_batch.json"))
    args = parser.parse_args()
    try:
        if args.command == "demo":
            report = run_comparison(load_demo(), time_limit=args.solve_seconds, repair_at=args.repair_at)
            write_json(args.output, report)
            print_comparison(report)
            print(f"Saved: {args.output.resolve()}")
        elif args.command == "development-batch":
            if not 1 <= args.count <= 100:
                raise ValueError("Count must be between 1 and 100")
            reports = []
            for seed in range(args.count):
                report = run_comparison(development_scenario(seed), time_limit=args.solve_seconds)
                reports.append(report)
                print(f"Development seed {seed}: validated all three candidates", flush=True)
            write_json(args.output, {"kind": "development_batch", "held_out": False, "reports": reports})
            print(f"Saved: {args.output.resolve()}")
        else:
            from .agent import function, supervise
            from .provider import ModelClient
            client = ModelClient(args.provider)
            if args.command == "smoke":
                models = client.models()
                if client.model not in models:
                    raise ValueError(f"Configured model {client.model} is absent from the provider catalog; verify hackathon access.")
                tool = function("acknowledge", "Acknowledge the connectivity test", {
                    "type": "object", "properties": {"ok": {"type": "boolean", "enum": [True]}},
                    "required": ["ok"], "additionalProperties": False})
                reply = client.complete([{"role": "user", "content": 'Call acknowledge with {"ok": true}.'}], [tool])
                calls = reply["message"].get("tool_calls", [])
                if not calls or calls[0]["function"]["name"] != "acknowledge" or json.loads(calls[0]["function"]["arguments"]) != {"ok": True}:
                    raise ValueError("Model did not return the expected tool call; provider integration is not verified")
                print(json.dumps({"provider": client.provider, "model": client.model, "tool_call_verified": True,
                                  "usage": reply["usage"], "seconds": reply["seconds"]}, indent=2))
            else:
                scenario = load_demo()
                reference, state, incident = prepare(scenario, time_limit=args.solve_seconds)
                result = supervise(client, scenario, state, reference, incident, time_limit=args.solve_seconds)
                write_json(args.output, result)
                print(f"{result['decision']} / {result['selected_policy']}")
                print(result["evidence_summary"])
                print(f"Saved: {args.output.resolve()}")
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
