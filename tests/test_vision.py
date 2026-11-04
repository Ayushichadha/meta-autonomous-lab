import base64
from io import BytesIO
import json
from types import SimpleNamespace
import pytest
from PIL import Image
from factory_lab.vision import validate_image, interpret_image
from factory_lab.provider import ModelClient, ProviderError


def image_url(size=(100,100)):
    out=BytesIO();Image.new('RGB',size,'white').save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


@pytest.mark.parametrize('url',['https://example.com/image.png','data:image/svg+xml;base64,AAAA',
    'data:image/png;base64,not-an-image','data:image/jpeg;base64,iVBORw0KGgo='])
def test_unsafe_or_invalid_images_rejected(url):
    with pytest.raises(ValueError):validate_image(url)


def test_large_dimensions_rejected_before_inference():
    with pytest.raises(ValueError,match='dimensions'):validate_image(image_url((2049,32)))


def test_vision_is_review_only_and_preserves_exact_text():
    text='CNC-A repair delayed by another 40 minutes.'
    class Client:
        model='muse-spark-1.3'
        def complete(self,messages,tools,**kwargs):
            assert messages[1]['content'][1]['type']=='image_url'
            return {'message':{'tool_calls':[{'function':{'name':'report_visible_maintenance',
                'arguments':json.dumps({'transcription':text,'observations':['Visible maintenance note.'],'uncertainties':[]})}}]},'estimated_cost_usd':.002}
    result=interpret_image(Client(),image_url())
    assert result['review_required'] and result['state_changed'] is False
    assert result['visual_report']['transcription']==text
    assert 'events' not in result and 'image' not in result


def test_vision_no_tool_response_cannot_create_fact():
    client=SimpleNamespace(model='muse-spark-1.3',complete=lambda *a,**k:{'message':{'content':'Machine repaired'}})
    with pytest.raises(RuntimeError,match='No complete visual report'):interpret_image(client,image_url())


def test_image_bytes_do_not_bypass_guard_or_count_as_text_tokens(monkeypatch,tmp_path):
    monkeypatch.setenv('META_API_KEY','test-key')
    client=ModelClient('meta',env_file=str(tmp_path/'absent'))
    reservations=[]
    client.ledger=SimpleNamespace(reserve=lambda model,amount:reservations.append(amount) or 'request',settle=lambda *a:.001)
    monkeypatch.setattr(client,'_request',lambda *a:{'choices':[{'message':{'content':'ok'},'finish_reason':'stop'}],'usage':{}})
    client.complete([{'role':'user','content':[{'type':'image_url','image_url':{'url':image_url()}}]}],[])
    assert len(reservations)==1 and .04 < reservations[0] < .1
    with pytest.raises(ProviderError,match='Only one'):
        client.complete([{'role':'user','content':[{'type':'image_url','image_url':{'url':image_url()}}]*2}],[])
    assert len(reservations)==1
