"""Single-request Gemini REST transport; local keys encrypted by Windows DPAPI."""
import base64
import ctypes
import json
import os
from pathlib import Path
import re
import httpx


def key_path():return Path(os.environ.get('FLUX_KEYS_PATH',str(Path.home()/'.flux/provider-keys.json')))


class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_uint32),('data',ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name!='nt':raise ValueError('Encrypted local key storage requires Windows.')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(out)):raise ValueError('Local key encryption failed.')
    try:return ctypes.string_at(out.data,out.size)
    finally:ctypes.windll.kernel32.LocalFree(out.data)


ALLOWED_PROVIDERS = {'gemini', 'groq', 'openrouter', 'together'}


def save_provider_key(provider,key):
    if provider not in ALLOWED_PROVIDERS:raise ValueError('Provider key is not supported.')
    key=key.strip()
    if key and (len(key)<8 or not re.fullmatch(r'[A-Za-z0-9_.:/-]+',key)):raise ValueError('API key format is invalid.')
    path=key_path();path.parent.mkdir(parents=True,exist_ok=True)
    data=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    if key:data[provider]=base64.b64encode(protect(key.encode())).decode('ascii')
    else:data.pop(provider,None)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data),encoding='utf-8');temp.replace(path)


def get_provider_key(provider):
    path=key_path()
    if not path.is_file():return ''
    try:
        encrypted=json.loads(path.read_text(encoding='utf-8')).get(provider)
        return protect(base64.b64decode(encrypted),True).decode() if encrypted else ''
    except (OSError,ValueError,KeyError):return ''


def purge_removed_provider_keys():
    """GapGPT is no longer a supported connection: drop any key stored earlier."""
    path=key_path()
    try:
        data=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        if 'gapgpt' in data:
            data.pop('gapgpt');temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data),encoding='utf-8');temp.replace(path)
    except (OSError,ValueError):pass


def save_key(key):save_provider_key('gemini',key)
def get_key():return get_provider_key('gemini')


async def generate(model, prompt, max_output=4000):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',model):raise ValueError('Gemini API model ID is invalid.')
    key=get_key()
    if not key:raise ValueError('کلید Gemini API را در تنظیمات اتصال وارد کنید.')
    body={'contents':[{'role':'user','parts':[{'text':prompt}]}], 'generationConfig':{'maxOutputTokens':max_output}}
    if model=='gemini-2.5-flash':body['generationConfig']['thinkingConfig']={'thinkingBudget':0}
    # No automatic retries, alternate endpoints, tool invocation or copied OAuth.
    async with httpx.AsyncClient(timeout=120,follow_redirects=False) as client:
        response=await client.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
            headers={'x-goog-api-key':key},json=body)
    if response.status_code!=200:raise ValueError('Gemini API returned HTTP '+str(response.status_code)+'. No automatic resend.')
    data=response.json();candidates=data.get('candidates') or []
    if not candidates or candidates[0].get('finishReason')!='STOP':raise ValueError('Gemini response is blocked or incomplete; it is not a successful artifact.')
    text='\n'.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
    if not text.strip():raise ValueError('Gemini returned no answer.')
    stats=data.get('usageMetadata') or {}
    return text,{'billing':'gemini-api','input_tokens':stats.get('promptTokenCount'),'output_tokens':stats.get('candidatesTokenCount'),
        'thought_tokens':stats.get('thoughtsTokenCount'),'cached_input_tokens':stats.get('cachedContentTokenCount'),
        'provider_usage':stats,'actual_cost_usd':None,'usage_available':bool(stats),'physical_requests':1}
