"""
Portal de Automação - backend (BFF) para o AWX / Ansible Automation Platform.

O navegador nunca recebe o token: só este backend fala com a API do AWX.
Os usuários entram com o login do LDAP/AD; o AWX vê um único usuário de serviço
(o dono do token), e o portal decide quem pode executar o quê:

  - template publicado = label PORTAL_LABEL ("portal") no AWX
  - quem pode usar      = labels "grupo:<grupo do LDAP>" no template
  - PORTAL_ADMIN_GROUP  = vê e executa todos os templates publicados
  - cada execução grava o usuário real na variável PORTAL_USER_VAR ("portal_user"),
    se o survey do template tiver essa pergunta

Variáveis de ambiente (LDAP_*: veja auth.py):
  AWX_URL, AWX_TOKEN      AWX e token do usuário de serviço (obrigatórias)
  AWX_API_PREFIX          /api/v2 (AWX) ou /api/controller/v2 (AAP 2.5+)
  AWX_VERIFY_SSL          "false" para certificado autoassinado
  PORTAL_LABEL            label que publica o template (padrão "portal")
  PORTAL_GROUP_PREFIX     prefixo das labels de grupo (padrão "grupo:")
  PORTAL_ADMIN_GROUP      grupo LDAP com acesso total (padrão "portal-admins")
  PORTAL_USER_VAR         variável do survey que recebe o usuário (padrão "portal_user")
  PORTAL_SESSION_SECRET   chave que assina o cookie de sessão (obrigatória em produção)
  PORTAL_SESSION_HOURS    duração da sessão (padrão 8)
  PORTAL_COOKIE_SECURE    "true" quando o portal estiver em HTTPS
  PORTAL_HISTORY_SIZE     execuções no histórico (padrão 10)
  PORTAL_STDOUT_MAX_KB    quanto da saída mostrar na tela, a partir do fim (padrão 256)
"""

import json
import logging
import os
import secrets
import time

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import auth

AWX_URL = os.environ.get("AWX_URL", "").rstrip("/")
AWX_TOKEN = os.environ.get("AWX_TOKEN", "")
API = os.environ.get("AWX_API_PREFIX", "/api/v2").rstrip("/")
VERIFY = os.environ.get("AWX_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
PORTAL_LABEL = os.environ.get("PORTAL_LABEL", "portal")
GROUP_PREFIX = os.environ.get("PORTAL_GROUP_PREFIX", "grupo:")
ADMIN_GROUP = os.environ.get("PORTAL_ADMIN_GROUP", "portal-admins")
USER_VAR = os.environ.get("PORTAL_USER_VAR", "portal_user")
HISTORY_SIZE = int(os.environ.get("PORTAL_HISTORY_SIZE", "10"))
STDOUT_MAX_BYTES = int(os.environ.get("PORTAL_STDOUT_MAX_KB", "256")) * 1024
SESSION_HOURS = int(os.environ.get("PORTAL_SESSION_HOURS", "8"))
SESSION_SECRET = os.environ.get("PORTAL_SESSION_SECRET", "")
COOKIE_SECURE = os.environ.get("PORTAL_COOKIE_SECURE", "false").lower() in ("true", "1", "yes")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FINISHED = {"successful", "failed", "error", "canceled"}

log = logging.getLogger("portal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_urlsafe(32)
    log.warning("PORTAL_SESSION_SECRET não definido: usando chave aleatória (sessões caem a cada restart).")

app = FastAPI(title="Portal de Automação")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="portal_session",
    max_age=SESSION_HOURS * 3600,
    same_site="lax",
    https_only=COOKIE_SECURE,
)


# ================================================================ AWX

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


def _labels(obj: dict) -> list[str]:
    return [l["name"] for l in obj.get("summary_fields", {}).get("labels", {}).get("results", [])]


# ================================================================ sessão e permissões

def current_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Faça login para continuar.")
    return user


def is_admin(user: dict) -> bool:
    return ADMIN_GROUP in user["groups"]


def can_use(user: dict, labels: list[str]) -> bool:
    """Template publicado e liberado para algum grupo do usuário (admins: todos os publicados)."""
    if PORTAL_LABEL and PORTAL_LABEL not in labels:
        return False
    if is_admin(user):
        return True
    allowed = {l[len(GROUP_PREFIX):] for l in labels if l.startswith(GROUP_PREFIX)}
    return bool(allowed & set(user["groups"]))


_tpl_cache: dict[int, tuple[float, dict]] = {}


def template(tid: int) -> dict:
    """Template do AWX com cache curto (as labels são consultadas a cada chamada)."""
    hit = _tpl_cache.get(tid)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    t = get(f"/job_templates/{tid}/").json()
    _tpl_cache[tid] = (time.time(), t)
    return t


def require_template(tid: int, user: dict) -> dict:
    t = template(tid)
    if not can_use(user, _labels(t)):
        raise HTTPException(404, "Automação não encontrada ou sem permissão.")
    return t


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    try:
        user = auth.authenticate(req.username, req.password)
    except auth.AuthError as e:
        log.info("login recusado: user=%s motivo=%s", req.username, e)
        time.sleep(1)  # freia tentativas em sequência
        raise HTTPException(401, str(e))
    request.session.clear()
    request.session["user"] = user
    log.info("login: user=%s grupos=%s", user["username"], ",".join(user["groups"]))
    return {**user, "admin": is_admin(user)}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {**user, "admin": is_admin(user)}


# ================================================================ catálogo e formulário

@app.get("/api/templates")
def list_templates(user: dict = Depends(current_user)):
    params = {"page_size": 200, "order_by": "name"}
    if PORTAL_LABEL:
        params["labels__name"] = PORTAL_LABEL
    data = get("/job_templates/", **params).json()
    hidden = {PORTAL_LABEL}
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t.get("description", ""),
            "labels": [l for l in _labels(t) if l not in hidden and not l.startswith(GROUP_PREFIX)],
        }
        for t in data.get("results", [])
        if can_use(user, _labels(t))
    ]


def _form(t: dict) -> dict:
    fields, has_user_var = [], False
    if t.get("ask_limit_on_launch"):
        fields.append({
            "kind": "limit", "variable": "limit", "type": "text", "required": True,
            "label": "Servidores ou grupo",
            "help": "Um host, uma lista separada por vírgula ou um grupo do inventário.",
            "default": "",
        })
    if t.get("survey_enabled"):
        spec = get(f"/job_templates/{t['id']}/survey_spec/").json()
        for q in spec.get("spec", []):
            if q["variable"] == USER_VAR:  # preenchido pelo backend, nunca pelo usuário
                has_user_var = True
                continue
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
    return {"id": t["id"], "name": t["name"], "description": t.get("description", ""),
            "fields": fields, "records_user": has_user_var}


@app.get("/api/templates/{tid}/form")
def template_form(tid: int, user: dict = Depends(current_user)):
    return _form(require_template(tid, user))


# ================================================================ execução

class LaunchRequest(BaseModel):
    limit: str | None = None
    extra_vars: dict = {}


@app.post("/api/templates/{tid}/launch")
def launch(tid: int, req: LaunchRequest, user: dict = Depends(current_user)):
    form = _form(require_template(tid, user))
    allowed = {f["variable"] for f in form["fields"] if f["kind"] == "survey"}
    extra = {k: v for k, v in req.extra_vars.items() if k in allowed}
    if form["records_user"]:
        extra[USER_VAR] = user["username"]  # sempre do login, nunca do formulário
    body = {"extra_vars": extra}
    if req.limit is not None and any(f["kind"] == "limit" for f in form["fields"]):
        body["limit"] = req.limit.strip()

    try:
        with awx() as c:
            r = c.post(f"/job_templates/{tid}/launch/", json=body)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Não foi possível falar com o AWX: {e}")

    if r.status_code >= 400:
        try:
            detail = r.json()
        except ValueError:
            detail = r.text
        log.info("launch recusado: user=%s template=%s awx=%s", user["username"], tid, r.status_code)
        raise HTTPException(400, {"awx_status": r.status_code, "awx_error": detail})

    jid = r.json()["job"]
    log.info("launch: user=%s template=%s job=%s limit=%s vars=%s",
             user["username"], tid, jid, body.get("limit", ""), sorted(extra))
    return {"job": jid}


# ================================================================ acompanhamento

def _extra(j: dict) -> dict:
    try:
        return json.loads(j.get("extra_vars") or "{}")
    except ValueError:
        return {}


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
        "portal_user": _extra(j).get(USER_VAR),
    }


def require_job(jid: int, user: dict) -> dict:
    """Job de um template que o usuário pode usar (vale para ver resultado e saída)."""
    j = get(f"/jobs/{jid}/").json()
    tid = (j.get("summary_fields", {}).get("job_template") or {}).get("id")
    if not tid:
        raise HTTPException(404, "Execução não encontrada ou sem permissão.")
    try:
        require_template(tid, user)
    except HTTPException:
        raise HTTPException(404, "Execução não encontrada ou sem permissão.")
    return j


@app.get("/api/jobs/{jid}")
def job_status(jid: int, user: dict = Depends(current_user)):
    j = require_job(jid, user)
    out = _job_summary(j)
    extra = _extra(j)
    extra.pop(USER_VAR, None)
    out.update({"extra_vars": extra, "results": None, "unreachable": []})  # password vem como $encrypted$
    if out["finished"]:
        out["results"] = (j.get("artifacts") or {}).get("results")
        summaries = get(f"/jobs/{jid}/job_host_summaries/", page_size=200).json()
        out["unreachable"] = [s["host_name"] for s in summaries.get("results", []) if s.get("dark")]
    return out


# ================================================================ histórico

_svc_user: dict = {}


def _svc_user_id() -> int:
    if "id" not in _svc_user:
        _svc_user["id"] = get("/me/").json()["results"][0]["id"]
    return _svc_user["id"]


@app.get("/api/jobs")
def job_history(user: dict = Depends(current_user)):
    """Últimas execuções feitas pelo portal: as do próprio usuário (admins: todas)."""
    # Busca uma janela maior e filtra aqui: permissão e dono vêm de labels e extra_vars.
    params = {"created_by": _svc_user_id(), "order_by": "-id", "page_size": max(HISTORY_SIZE * 5, 50)}
    data = None
    if PORTAL_LABEL:
        try:
            data = get("/jobs/", **params, job_template__labels__name=PORTAL_LABEL).json()
        except httpx.HTTPStatusError:
            data = None  # AWX sem suporte ao filtro: cai para todos os jobs do usuário de serviço
    if data is None:
        data = get("/jobs/", **params).json()

    out = []
    for j in data.get("results", []):
        if "extra_vars" not in j:  # algumas versões não trazem extra_vars na listagem
            j = get(f"/jobs/{j['id']}/").json()
        s = _job_summary(j)
        if not s["template_id"]:
            continue
        if not is_admin(user) and s["portal_user"] != user["username"]:
            continue
        try:
            require_template(s["template_id"], user)
        except HTTPException:
            continue
        out.append(s)
        if len(out) >= HISTORY_SIZE:
            break
    return out


# ================================================================ saída do job

@app.get("/api/jobs/{jid}/stdout")
def job_stdout(jid: int, user: dict = Depends(current_user)):
    require_job(jid, user)
    # "txt" é recusado pelo AWX acima de ~1 MB; "txt_download" sempre devolve tudo.
    text = get(f"/jobs/{jid}/stdout/", format="txt_download").text
    size = len(text.encode())
    truncated = size > STDOUT_MAX_BYTES
    if truncated:
        tail = text.encode()[-STDOUT_MAX_BYTES:].decode(errors="ignore")
        text = tail[tail.find("\n") + 1:]  # mostra o final, onde ficam o resultado e o PLAY RECAP
    return {"stdout": text, "truncated": truncated, "size": size}


@app.get("/api/jobs/{jid}/stdout/download")
def job_stdout_download(jid: int, user: dict = Depends(current_user)):
    require_job(jid, user)
    text = get(f"/jobs/{jid}/stdout/", format="txt_download").text
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="job-{jid}.txt"'})


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ================================================================ frontend

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
