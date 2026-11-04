"""Short, reviewed maintenance dictation using Muse Voice Transcribe."""
import base64
import hashlib
from io import BytesIO
import re
import wave

MAX_SECONDS = 20


def validate_audio(data_url: str):
    match=re.fullmatch(r'data:audio/wav;base64,([A-Za-z0-9+/=]+)',data_url)
    if not match or len(data_url)>1_400_000:
        raise ValueError('Use a mono PCM WAV recording of at most 20 seconds.')
    try:
        raw=base64.b64decode(match[1],validate=True)
        if len(raw)>1_000_000:raise ValueError('Audio upload is too large.')
        with wave.open(BytesIO(raw),'rb') as audio:
            if audio.getnchannels()!=1 or audio.getsampwidth()!=2 or audio.getframerate() not in {16000,24000} or audio.getcomptype()!='NONE':
                raise ValueError('Audio must be mono 16-bit PCM WAV at 16 or 24 kHz.')
            duration=audio.getnframes()/audio.getframerate()
            if not 0<duration<=MAX_SECONDS:raise ValueError('Audio must be between 0 and 20 seconds.')
            if len(audio.readframes(audio.getnframes()))!=audio.getnframes()*2:
                raise ValueError('Audio is truncated.')
    except (wave.Error,EOFError):
        raise ValueError('The audio could not be decoded.') from None
    return raw,duration,hashlib.sha256(raw).hexdigest()
