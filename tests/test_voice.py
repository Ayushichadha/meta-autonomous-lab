import base64
from io import BytesIO
import wave
from types import SimpleNamespace
import pytest
from factory_lab.voice import validate_audio
from factory_lab.provider import ModelClient
from factory_lab.budget import usage_cost,configured_limit


def wav_url(seconds=1,channels=1,rate=24000):
    out=BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\0\0'*int(seconds*rate*channels))
    return 'data:audio/wav;base64,'+base64.b64encode(out.getvalue()).decode()


@pytest.mark.parametrize('url',['https://example.com/a.wav','data:audio/wav;base64,AAAA',wav_url(channels=2),wav_url(rate=8000),wav_url(seconds=21)])
def test_audio_rejected_before_request(url):
    with pytest.raises(ValueError):validate_audio(url)


def test_duration_billing_uses_audio_not_tokens():
    assert usage_cost('muse-voice-transcribe-1.0',{'audioDurationMs':10499})==10*.18/3600
    assert usage_cost('muse-voice-transcribe-1.0',{}) is None


def test_voice_reserves_before_request_and_never_changes_state(monkeypatch,tmp_path):
    monkeypatch.setenv('META_API_KEY','test-key')
    client=ModelClient('meta',env_file=str(tmp_path/'none'));events=[]
    client.ledger=SimpleNamespace(reserve=lambda *a:events.append('reserve') or 'id',settle=lambda *a:.00005)
    def request(*a,**kw):
        events.append('request');assert kw['files']['audio'][0]=='maintenance.wav'
        return {'transcript':'CNC-A is down.','audioDurationMs':1000}
    monkeypatch.setattr(client,'_request',request)
    report=client.transcribe_audio(wav_url())
    assert events==['reserve','request']
    assert report['model']=='muse-voice-transcribe-1.0' and report['review_required'] and not report['state_changed']


def test_configured_cap_cannot_be_unbounded(monkeypatch):
    monkeypatch.setenv('FACTORY_META_LIMIT_USD','3');assert configured_limit()==3
    monkeypatch.setenv('FACTORY_META_LIMIT_USD','150')
    with pytest.raises(ValueError):configured_limit()
