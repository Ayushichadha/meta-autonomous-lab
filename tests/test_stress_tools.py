import copy
import pytest
from factory_lab.experiments import experiment,stress_test_plan
from factory_lab.agent import supervise
from test_agent import context,ScriptedClient


def test_stress_trial_preserves_inputs_and_explicit_assumption():
    scenario,state,reference,incident=context();before=copy.deepcopy(state)
    candidate=experiment(scenario,state,reference,incident,'preserve',.2)
    result=stress_test_plan(scenario,state,reference,incident,candidate,30)
    assert result['repair_assumptions'][incident.machine]==incident.estimated_repair_at+30
    assert state==before and result['metrics']['weighted_tardiness_minutes']>=result['nominal_weighted_delay']
    with pytest.raises(ValueError):stress_test_plan(scenario,state,reference,incident,candidate,999)


def test_supervisor_requests_bounded_stress_and_caches_duplicate():
    client=ScriptedClient([
        ('stress_test_plan',{'policy':'preserve','extra_delay_minutes':30,'hypothesis':'Does another half hour threaten deliveries?'}),
        ('stress_test_plan',{'policy':'preserve','extra_delay_minutes':30,'hypothesis':'Repeat the same assumption.'}),
        ('select_plan',{'policy':'preserve','evidence_summary':'Measured fixture result.'})])
    result=supervise(client,*context(),time_limit=.2,enable_stress_tests=True)
    assert len(result['diagnostic_trials'])==1 and result['tool_profile']=='bounded_stress_v3'
    assert any(t['result'].get('cache_hit') for t in result['trace'])


def test_stress_tool_not_enabled_for_old_protocol():
    client=ScriptedClient([('stress_test_plan',{'policy':'preserve','extra_delay_minutes':30,'hypothesis':'Try'}),
        ('select_plan',{'policy':'preserve','evidence_summary':'Fixture'})])
    result=supervise(client,*context(),time_limit=.2)
    assert not result['diagnostic_trials'] and any(t['result'].get('error') for t in result['trace'])
