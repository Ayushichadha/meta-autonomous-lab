import copy
import json
from pathlib import Path

import pytest

from factory_lab.branching import run_note_branch
from factory_lab.domain import Snapshot
from factory_lab.notes import MaintenanceClaim, NoteExtraction, TimeClaim, validate_extraction
from factory_lab.scenarios import load_demo


def claim(note, *, machine="CNC-A", mode="delay_previous", minutes=40, timing="delayed by another 40 minutes", kind="repair_estimate"):
    return MaintenanceClaim(kind=kind, machine=machine, machine_evidence=machine,
                            evidence=note, timing=TimeClaim(mode=mode, minutes=minutes, evidence=timing))


def state():
    return Snapshot(now=55, available_at={"CNC-A": 120})


def test_delay_is_relative_to_previous_estimate_not_current_time():
    note = "CNC-A repair delayed by another 40 minutes."
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[claim(note)]))
    assert result["status"] == "validated"
    assert result["events"][0]["estimated_repair_at"] == 160


def test_time_quote_can_be_a_grounded_subphrase_of_explicit_delay():
    note = "CNC-A repair delayed by another 40 minutes."
    proposed = claim(note,timing="by another 40 minutes")
    result = validate_extraction(note,load_demo(),state(),NoteExtraction(claims=[proposed]))
    assert result["status"] == "validated" and result["events"][0]["estimated_repair_at"] == 160


@pytest.mark.parametrize("note,mode,minutes,evidence,expected", [
    ("CNC-A repair expected in 40 minutes.", "from_now", 40, "in 40 minutes", 95),
    ("CNC-A repair expected at minute 140.", "absolute_minute", 140, "at minute 140", 140)])
def test_explicit_time_modes(note, mode, minutes, evidence, expected):
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[claim(note,mode=mode,minutes=minutes,timing=evidence)]))
    assert result["status"] == "validated" and result["events"][0]["estimated_repair_at"] == expected


def test_missing_estimate_asks_clarification_without_applying_any_fact():
    note = "CNC-A is down."
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[claim(note, mode="not_given", minutes=None, timing="")]))
    assert result["status"] == "clarification_required"
    assert result["events"] == []


def test_available_notice_does_not_manufacture_a_repair():
    note = "INSPECT remains available."
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[claim(note,machine="INSPECT",kind="available_notice",mode="not_given",minutes=None,timing="")]))
    assert result["status"] == "validated" and result["events"] == []
    assert result["notices"][0]["state_change"] is False


def test_unknown_machine_cannot_be_replaced_with_context_guess():
    note = "CNC-Z repair delayed by another 40 minutes."
    proposed = claim(note).model_copy(update={"context_reference": True, "machine_evidence": ""})
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[proposed]))
    assert result["status"] == "rejected" and not result["events"]


def test_context_reference_requires_exactly_one_known_outage():
    note = "Repair delayed by another 40 minutes."
    proposed = claim(note).model_copy(update={"context_reference": True, "machine_evidence": ""})
    valid = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[proposed]))
    assert valid["status"] == "validated"
    ambiguous = validate_extraction(note, load_demo(), Snapshot(now=55, available_at={"CNC-A":120,"CNC-B":110}), NoteExtraction(claims=[proposed]))
    assert ambiguous["status"] == "clarification_required" and not ambiguous["events"]


@pytest.mark.parametrize("note", ["CNC-A is not repaired.", "CNC-A will be repaired in 40 minutes."])
def test_expected_or_negated_repair_does_not_restart_machine(note):
    proposed = claim(note,kind="repaired",mode="not_given",minutes=None,timing="")
    result = validate_extraction(note, load_demo(), state(), NoteExtraction(claims=[proposed]))
    assert result["status"] != "validated" and not result["events"]


def test_fabricated_quote_and_conflicting_claims_fail_atomically():
    note = "CNC-A repair expected in 20 minutes."
    fabricated = claim(note,mode="from_now",timing="in 40 minutes")
    assert validate_extraction(note,load_demo(),state(),NoteExtraction(claims=[fabricated]))["events"] == []
    real = claim(note,mode="from_now",minutes=20,timing="in 20 minutes")
    result = validate_extraction(note,load_demo(),state(),NoteExtraction(claims=[real,real]))
    assert result["status"] == "rejected" and not result["events"]


def test_branch_preserves_source_and_completed_work():
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root/'results/demo/meta-sequential-demo.json').read_text())
    before = copy.deepcopy(source)
    index = next(i for i,f in enumerate(source['frames']) if f['time'] == 55)
    note = "CNC-A repair delayed by another 40 minutes."
    extraction = NoteExtraction(claims=[claim(note)])
    observation = Snapshot.model_validate(source['frames'][index]['state'])
    interpretation = validate_extraction(note,load_demo(),observation,extraction)
    interpretation['note'] = note
    branch = run_note_branch(source,index,interpretation)
    assert branch['complete'] and branch['branch']['original_recording_unchanged']
    assert source == before
    final = branch['frames'][-1]['state']['progress']
    for operation, progress in observation.progress.items():
        if progress.completed_at is not None:
            assert final[operation] == progress.model_dump()
    updated = next(f for f in branch['frames'] if f['time'] == 55 and f['events'])
    assert updated['state']['available_at']['CNC-A'] == 160


def test_branch_revalidates_claims_not_forged_validated_status():
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root/'results/demo/meta-sequential-demo.json').read_text())
    note = "CNC-A repair expected in 20 minutes."
    interpretation = {'note':note,'status':'validated','proposed_claims':NoteExtraction(claims=[claim(note)]).model_dump()}
    with pytest.raises(ValueError,match='fully validated'):
        run_note_branch(source,1,interpretation)
