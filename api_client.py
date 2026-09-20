"""Frontend API client for Spectre Impact."""
import os
from typing import Any
import requests
API_URL=os.getenv("SPECTRE_BACKEND_URL","http://localhost:8000").rstrip("/")
def _url(path): return f"{API_URL}/{path.lstrip('/')}"
def post_json_detailed(path,payload:dict[str,Any],timeout:int=30):
    try:
        r=requests.post(_url(path),json=payload,timeout=timeout)
        try: data=r.json()
        except Exception: data={"message":r.text or ""}
        if not r.ok: return False,data if isinstance(data,dict) else {"message":str(data)},r.status_code
        return True,data if isinstance(data,dict) else {"data":data},r.status_code
    except requests.RequestException as exc: return False,{"error":str(exc)},None
def post_json(path,payload,timeout=30):
    ok,data,_=post_json_detailed(path,payload,timeout); return ok,data
def get_json_detailed(path,timeout=10):
    try:
        r=requests.get(_url(path),timeout=timeout)
        try: data=r.json()
        except Exception: data={"message":r.text or ""}
        if not r.ok: return False,data if isinstance(data,dict) else {"message":str(data)},r.status_code
        return True,data,r.status_code
    except requests.RequestException as exc: return False,{"error":str(exc)},None
def get_json(path,timeout=10):
    ok,data,_=get_json_detailed(path,timeout); return ok,data
def post_bytes(path,payload,timeout=60):
    try:
        r=requests.post(_url(path),json=payload,timeout=timeout)
        if not r.ok: return False,b"",r.text or f"HTTP {r.status_code}"
        return True,r.content,r.headers.get("content-type","audio/mpeg")
    except requests.RequestException as exc: return False,b"",str(exc)
def post_multipart(path,files,data=None,timeout=60):
    try:
        r=requests.post(_url(path),files=files,data=data or {},timeout=timeout)
        try: payload=r.json()
        except Exception: payload={"message":r.text or ""}
        if not r.ok: return False,payload if isinstance(payload,dict) else {"message":str(payload)},r.status_code
        return True,payload if isinstance(payload,dict) else {"data":payload},r.status_code
    except requests.RequestException as exc: return False,{"error":str(exc)},None
