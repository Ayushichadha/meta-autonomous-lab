"""Synthetic development inputs. Seeds here are NOT held-out evaluation evidence."""

from importlib.resources import files
import random

from .domain import Scenario


def load_demo() -> Scenario:
    return Scenario.model_validate_json(files("factory_lab").joinpath("scenarios/component_shop.json").read_text())


def development_scenario(seed: int) -> Scenario:
    rng = random.Random(seed)
    data = load_demo().model_dump()
    data["name"] = f"Synthetic development shop / seed {seed}"
    for order in data["orders"]:
        order["due"] += rng.randint(-15, 25)
        for op in order["operations"]:
            adjustment = rng.randint(-3, 5)
            op["durations"] = {machine: max(1, duration + adjustment) for machine, duration in op["durations"].items()}
    return Scenario.model_validate(data)
