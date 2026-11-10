"""
Portal de Automação - backend (BFF) para o AWX / Ansible Automation Platform.

O navegador nunca recebe o token: só este backend fala com a API do AWX.

Variáveis de ambiente:
  AWX_URL         URL base do AWX, ex.: https://awx.minha-vm.local  (obrigatória)
  AWX_TOKEN       token OAuth/PAT do AWX com permissão Execute nos templates (obrigatória)
  AWX_API_PREFIX  prefixo da API. AWX: /api/v2   AAP 2.5+: /api/controller/v2   (padrão /api/v2)
  AWX_VERIFY_SSL  "false" para aceitar certificado autoassinado (padrão true)
  PORTAL_LABEL    só mostra templates com esta label no AWX (padrão "portal"; vazio = todos)
  PORTAL_HISTORY_SIZE   quantas execuções mostrar no histórico (padrão 10)
  PORTAL_STDOUT_MAX_KB  quanto da saída do job mostrar na tela, a partir do fim (padrão 256)
"""

import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

AWX_URL = os.environ.get("AWX_URL", "").rstrip("/")
AWX_TOKEN = os.environ.get("AWX_TOKEN", "")
API = os.environ.get("AWX_API_PREFIX", "/api/v2").rstrip("/")
VERIFY = os.environ.get("AWX_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
PORTAL_LABEL = os.environ.get("PORTAL_LABEL", "portal")
HISTORY_SIZE = int(os.environ.get("PORTAL_HISTORY_SIZE", "10"))
STDOUT_MAX_BYTES = int(os.environ.get("PORTAL_STDOUT_MAX_KB", "256")) * 1024

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FINISHED = {"successful", "failed", "error", "canceled"}

app = FastAPI(title="Portal de Automação")


def awx() -> httpx.Client:
    if not AWX_URL or not AWX_TOKEN:
        raise HTTPException(500, "Portal sem configuração: defina AWX_URL e AWX_TOKEN.")
    return httpx.Client(
        base_url=AWX_URL + API,
        headers={"Authorization": f"Bearer {AWX_TOKEN}"},
        verify=VERIFY,
        timeout=30,
    )


def get(path: str, **params):
    try:
        with awx() as c:
            r = c.get(path, params=params or None)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Não foi possível falar com o AWX: {e}")
    if r.status_code == 404:
        raise HTTPException(404, "Não encontrado no AWX.")
    if r.status_code in (401, 403):
        raise HTTPException(502, "O AWX recusou o token do portal (401/403).")
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- catálogo

@app.get("/api/templates")
def list_templates():
    params = {"page_size": 100, "order_by": "name"}
    if PORTAL_LABEL:
        params["labels__name"] = PORTAL_LABEL
    data = get("/job_templates/", **params).json()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t.get("description", ""),
            "labels": [l["name"] for l in t.get("summary_fields", {}).get("labels", {}).get("results", [])
                       if l["name"] != PORTAL_LABEL],
        }
        for t in data.get("results", [])
    ]


# ---------------------------------------------------------------- formulário

@app.get("/api/templates/{tid}/form")
def template_form(tid: int):
    t = get(f"/job_templates/{tid}/").json()
    if PORTAL_LABEL:
        names = [l["name"] for l in t.get("summary_fields", {}).get("labels", {}).get("results", [])]
        if PORTAL_LABEL not in names:
            raise HTTPException(404, "Template não publicado no portal.")

    fields = []
    if t.get("ask_limit_on_launch"):
        fields.append({
            "kind": "limit", "variable": "limit", "type": "text", "required": True,
            "label": "Servidores ou grupo",
            "help": "Um host, uma lista separada por vírgula ou um grupo do inventário.",
            "default": "",
        })

    if t.get("survey_enabled"):
        spec = get(f"/job_templates/{tid}/survey_spec/").json()
        for q in spec.get("spec", []):
            choices = q.get("choices") or []
            if isinstance(choices, str):
                choices = [c for c in choices.split("\n") if c]
            fields.append({
                "kind": "survey",
                "variable": q["variable"],
                "type": q.get("type", "text"),
                "required": bool(q.get("required")),
                "label": q.get("question_name") or q["variable"],
                "help": q.get("question_description", ""),
                "default": "" if q.get("type") == "password" else q.get("default", ""),
                "choices": choices,
                "min": q.get("min"),
                "max": q.get("max"),
            })

    return {"id": t["id"], "name": t["name"], "description": t.get("description", ""), "fields": fields}


# ---------------------------------------------------------------- execução

class LaunchRequest(BaseModel):
    limit: str | None = None
    extra_vars: dict = {}


@app.post("/api/templates/{tid}/launch")
def launch(tid: int, req: LaunchRequest):
    form = template_form(tid)  # garante que o template está publicado no portal
    allowed = {f["variable"] for f in form["fields"] if f["kind"] == "survey"}
    body = {"extra_vars": {k: v for k, v in req.extra_vars.items() if k in allowed}}
    if req.limit is not None and any(f["kind"] == "limit" for f in form["fields"]):
        body["limit"] = req.limit.strip()

    try:
        with awx() as c:
            r = c.post(f"/job_templates/{tid}/launch/", json=body)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Não foi possível falar com o AWX: {e}")

    if r.status_code >= 400:
        # Repassa a mensagem do AWX (ex.: survey obrigatório, limit inválido)
        try:
            detail = r.json()
        except ValueError:
            detail = r.text
        raise HTTPException(400, {"awx_status": r.status_code, "awx_error": detail})

    return {"job": r.json()["job"]}


# ---------------------------------------------------------------- acompanhamento

def _job_summary(j: dict) -> dict:
    sf = j.get("summary_fields", {})
    jt = sf.get("job_template") or sf.get("unified_job_template") or {}
    return {
        "id": j["id"],
        "template_id": jt.get("id"),
        "template_name": jt.get("name") or j.get("name"),
        "status": j["status"],
        "finished": j["status"] in FINISHED,
        "started": j.get("started"),
        "elapsed": j.get("elapsed"),
        "limit": j.get("limit") or "",
    }


@app.get("/api/jobs/{jid}")
def job_status(jid: int):
    j = get(f"/jobs/{jid}/").json()
    out = _job_summary(j)
    try:
        extra = json.loads(j.get("extra_vars") or "{}")
    except ValueError:
        extra = {}
    out.update({
        "extra_vars": extra,  # o AWX já mascara campos password como $encrypted$
        "launched_by": (j.get("summary_fields", {}).get("created_by") or {}).get("username"),
        "results": None,
        "unreachable": [],
    })
    if out["finished"]:
        artifacts = j.get("artifacts") or {}
        out["results"] = artifacts.get("results")
        summaries = get(f"/jobs/{jid}/job_host_summaries/", page_size=200).json()
        out["unreachable"] = [s["host_name"] for s in summaries.get("results", []) if s.get("dark")]
    return out


# ---------------------------------------------------------------- histórico

_me_cache: dict = {}


def _my_user_id() -> int:
    if "id" not in _me_cache:
        _me_cache["id"] = get("/me/").json()["results"][0]["id"]
    return _me_cache["id"]


@app.get("/api/jobs")
def job_history():
    """Últimas execuções disparadas pelo portal (usuário do token), mais recentes primeiro."""
    params = {"created_by": _my_user_id(), "order_by": "-id", "page_size": HISTORY_SIZE}
    data = None
    if PORTAL_LABEL:
        try:
            data = get("/jobs/", **params, job_template__labels__name=PORTAL_LABEL).json()
        except httpx.HTTPStatusError:
            data = None  # AWX sem suporte ao filtro: cai para todos os jobs do usuário do portal
    if data is None:
        data = get("/jobs/", **params).json()
    return [_job_summary(j) for j in data.get("results", [])]


# ---------------------------------------------------------------- saída do job

@app.get("/api/jobs/{jid}/stdout")
def job_stdout(jid: int):
    # "txt" é recusado pelo AWX acima de ~1 MB; "txt_download" sempre devolve tudo.
    text = get(f"/jobs/{jid}/stdout/", format="txt_download").text
    size = len(text.encode())
    truncated = size > STDOUT_MAX_BYTES
    if truncated:
        # mostra o final, onde ficam o resultado e o PLAY RECAP
        tail = text.encode()[-STDOUT_MAX_BYTES:].decode(errors="ignore")
        text = tail[tail.find("\n") + 1:]
    return {"stdout": text, "truncated": truncated, "size": size}


@app.get("/api/jobs/{jid}/stdout/download")
def job_stdout_download(jid: int):
    text = get(f"/jobs/{jid}/stdout/", format="txt_download").text
    return PlainTextResponse(
        text, headers={"Content-Disposition": f'attachment; filename="job-{jid}.txt"'}
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------------------------------------------------------- frontend

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
