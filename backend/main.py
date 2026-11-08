"""GLITCHLAB: explainable, deterministic pre-publication checks.
Demo intentionally uses SQLite and a single isolated demonstration workspace.
No authentication or tenant isolation is claimed: do not put sensitive data here.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager
from typing import Literal
import os
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"))
from intelligence import enabled, assess, propose_rules, AIUnavailable
from smart_patch import preview_smart_patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from deployment_guard import DemoGuard, demo_mode, allowed_origins
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
# Set GLITCHLAB_DB_PATH to an absolute path on a persistent disk when hosted.
# Local development continues to use the original backend/glitchlab.db file.
_DB_OVERRIDE = os.getenv('GLITCHLAB_DB_PATH', '').strip()
DB = Path(_DB_OVERRIDE).expanduser() if _DB_OVERRIDE else ROOT / "glitchlab.db"
if _DB_OVERRIDE and not DB.is_absolute():
    raise RuntimeError('GLITCHLAB_DB_PATH must be an absolute path')
MODE = demo_mode()
ORIGINS = allowed_origins()
if MODE == 'public' and not _DB_OVERRIDE:
    raise RuntimeError('Public demo requires GLITCHLAB_DB_PATH on a persistent volume')
DB.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="GLITCHLAB_ API", version="0.3.0")
# Middleware order: CORS wraps the guard so even limit/error replies have CORS headers.
app.add_middleware(DemoGuard, public=(MODE == 'public'))
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type"])

@contextmanager
def db():
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout = 15000")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def ident():
    return str(uuid4())

class RuleIn(BaseModel):
    code: str = Field(min_length=2,max_length=32)
    category: Literal["terminology","fact","claim","tone"]
    title: str = Field(min_length=2,max_length=120)
    explanation: str = Field(min_length=5,max_length=500)
    source: str = Field(min_length=3,max_length=300)
    pattern: str = Field(min_length=1,max_length=160)
    replacement: str = Field(default="",max_length=250)
    active: bool = True
    channels: list[Literal["social", "email", "website", "general", "all"]] = Field(default_factory=lambda: ["all"], min_length=1, max_length=4)

class RuleChannelsIn(BaseModel):
    channels: list[Literal["social", "email", "website", "general", "all"]] = Field(min_length=1, max_length=4)

class DraftIn(BaseModel):
    title: str = Field(min_length=1,max_length=120)
    channel: Literal["social","email","website","general"] = "general"
    content: str = Field(min_length=1,max_length=12000)

class RevisionIn(BaseModel):
    content: str = Field(min_length=1,max_length=12000)

class ReviewIn(BaseModel):
    decision: Literal["approved","changes_requested"]
    reviewer: str = Field(min_length=1,max_length=80)
    comment: str = Field(default="",max_length=1000)

SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL, category TEXT NOT NULL,title TEXT NOT NULL, explanation TEXT NOT NULL, source TEXT NOT NULL,pattern TEXT NOT NULL,replacement TEXT NOT NULL,active INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY,title TEXT NOT NULL,channel TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions (id TEXT PRIMARY KEY,draft_id TEXT NOT NULL,number INTEGER NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(draft_id) REFERENCES drafts(id),UNIQUE(draft_id,number));
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,draft_id TEXT NOT NULL,version_id TEXT NOT NULL,created_at TEXT NOT NULL,rule_snapshot TEXT NOT NULL,FOREIGN KEY(version_id) REFERENCES versions(id));
CREATE TABLE IF NOT EXISTS findings (id TEXT PRIMARY KEY,run_id TEXT NOT NULL,rule_code TEXT NOT NULL,category TEXT NOT NULL,source TEXT NOT NULL,title TEXT NOT NULL,explanation TEXT NOT NULL,matched_text TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,suggestion TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY,draft_id TEXT NOT NULL,version_id TEXT NOT NULL,decision TEXT NOT NULL,reviewer TEXT NOT NULL,comment TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(draft_id) REFERENCES drafts(id));
"""
SEEDS = [
    ("BR-101","fact","Battery life specification","The approved NovaCell X specification permits claims of up to 48 hours, not 72 hours.","NovaCell X product fact sheet · v1 §2","72\\s*[- ]?hour(?:s)?","up to 48-hour"),
    ("BR-102","claim","Unsupported superiority claim","Claims such as 'best in India' require substantiation not available in the approved source library.","Promotional claims policy · v1 §4","best\\s+(?:battery\\s+)?in\\s+India","a powerful choice"),
    ("BR-103","claim","Unqualified guarantee","Do not promise guaranteed outcomes unless an approved guarantee is explicitly documented.","Promotional claims policy · v1 §3","guaranteed","designed for"),
    ("BR-104","terminology","Preferred product naming","Use the approved name NovaCell X, not Nova Cell X.","Brand language guide · v1 §1","Nova\\s+Cell\\s+X","NovaCell X"),
    ("BR-105","tone","Restricted hyperbole","Avoid the word revolutionary in official product descriptions.","Brand voice guide · v1 §5","revolutionary","new"),
]

def initialize():
    with db() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(SCHEMA)
        # Add-only SQLite migration: keep all existing rules, drafts, and history.
        existing_columns = {r["name"] for r in con.execute("PRAGMA table_info(rules)")}
        if "channels" not in existing_columns:
            con.execute("""ALTER TABLE rules ADD COLUMN channels TEXT NOT NULL DEFAULT '["all"]'""")
        con.execute("""CREATE TABLE IF NOT EXISTS sources
        (id TEXT PRIMARY KEY, filename TEXT NOT NULL, kind TEXT NOT NULL,
        content TEXT NOT NULL, created_at TEXT NOT NULL)""")
        if con.execute("SELECT COUNT(*) AS n FROM rules").fetchone()["n"] == 0:
            for code,category,title,explanation,source,pattern,replacement in SEEDS:
                con.execute("""INSERT INTO rules (id, code, category, title, explanation, source, pattern, replacement, active, version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(ident(),code,category,title,explanation,source,pattern,replacement,1,1,now()))
initialize()

CHANNELS = ("social", "email", "website", "general")

def normalized_channels(value):
    channels = list(dict.fromkeys(value))
    return ["all"] if "all" in channels else channels

def rule_is_applicable(rule, channel: str) -> bool:
    values = rule.get("channels", ["all"])
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except (TypeError, ValueError):
            values = ["all"]
    return "all" in values or channel in values

def rows(data):
    result = [dict(r) for r in data]
    for item in result:
        if "channels" in item:
            try:
                item["channels"] = json.loads(item["channels"])
            except (TypeError, ValueError):
                item["channels"] = ["all"]
    return result

def applicable_rules(con, channel: str):
    return [r for r in rows(con.execute("SELECT * FROM rules WHERE active=1 ORDER BY code"))
            if rule_is_applicable(r, channel)]

def latest(con,draft_id):
    draft=con.execute("SELECT * FROM drafts WHERE id=?",(draft_id,)).fetchone()
    if draft is None: raise HTTPException(404,"Draft not found")
    version=con.execute("SELECT * FROM versions WHERE draft_id=? ORDER BY number DESC LIMIT 1",(draft_id,)).fetchone()
    return dict(draft),dict(version)

@app.get("/health")
def health(): return {"ok":True,"service":"GLITCHLAB_","version":"0.3.0", "ai_enabled":enabled(), "mode": MODE}

@app.get("/rules")
def rules():
    with db() as con: return rows(con.execute("SELECT * FROM rules ORDER BY code"))

@app.post("/rules",status_code=201)
def add_rule(body:RuleIn):
    try: re.compile(body.pattern,re.IGNORECASE)
    except re.error: raise HTTPException(422,"Invalid regular expression")
    with db() as con:
        try: con.execute("""INSERT INTO rules (id, code, category, title, explanation, source, pattern,
               replacement, active, version, created_at, channels) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
               (ident(),body.code,body.category,body.title,body.explanation,body.source,body.pattern,
                body.replacement,int(body.active),1,now(),json.dumps(normalized_channels(body.channels))))
        except sqlite3.IntegrityError: raise HTTPException(409,"Rule code already exists")
    return {"ok":True,"code":body.code}

@app.patch("/rules/{rule_code}/channels")
def set_rule_channels(rule_code: str, body: RuleChannelsIn):
    """Demo policy admin: edit channel scope without changing historical runs."""
    scope = normalized_channels(body.channels)
    with db() as con:
        cursor = con.execute("UPDATE rules SET channels=?, version=version+1 WHERE code=?",
                             (json.dumps(scope), rule_code))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Rule not found")
        rule = con.execute("SELECT * FROM rules WHERE code=?", (rule_code,)).fetchone()
    return {**dict(rule), "channels": scope}

@app.get("/drafts")
def list_drafts():
    with db() as con:
        return rows(con.execute("SELECT d.*,MAX(v.number) AS version FROM drafts d JOIN versions v ON d.id=v.draft_id GROUP BY d.id ORDER BY d.created_at DESC"))

@app.post("/drafts",status_code=201)
def new_draft(body:DraftIn):
    draft_id,version_id=ident(),ident()
    with db() as con:
        con.execute("INSERT INTO drafts VALUES (?,?,?,?)",(draft_id,body.title,body.channel,now()))
        con.execute("INSERT INTO versions VALUES (?,?,?,?,?)",(version_id,draft_id,1,body.content,now()))
    return {"id":draft_id,"version_id":version_id,"number":1}

@app.get("/drafts/{draft_id}")
def get_draft(draft_id:str):
    with db() as con:
        draft,version=latest(con,draft_id)
        versions=rows(con.execute("SELECT * FROM versions WHERE draft_id=? ORDER BY number DESC",(draft_id,)))
        reviews=rows(con.execute("SELECT * FROM reviews WHERE draft_id=? ORDER BY created_at DESC",(draft_id,)))
        runs=rows(con.execute("SELECT id,version_id,created_at FROM runs WHERE draft_id=? ORDER BY created_at DESC",(draft_id,)))
        return {**draft,"current":version,"versions":versions,"reviews":reviews,"runs":runs}

@app.post("/drafts/{draft_id}/run")
def run_tests(draft_id:str):
    import json
    with db() as con:
        draft,version=latest(con,draft_id)
        ruleset=applicable_rules(con, draft["channel"])
        run_id=ident()
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?)",(run_id,draft_id,version["id"],now(),json.dumps([{"code":r["code"],"version":r["version"],"source":r["source"], "channels":r["channels"]} for r in ruleset])))
        findings=[]
        for rule in ruleset:
            try: matches=list(re.finditer(rule["pattern"],version["content"],flags=re.IGNORECASE))
            except re.error: continue
            for match in matches:
                entry={"id":ident(),"run_id":run_id,"rule_code":rule["code"],"category":rule["category"],"source":rule["source"],"title":rule["title"],"explanation":rule["explanation"],"matched_text":match.group(),"start":match.start(),"end":match.end(),"suggestion":rule["replacement"]}
                con.execute("INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?)",tuple(entry.values()))
                findings.append(entry)
        return {"run_id":run_id,"draft_id":draft_id,"version_id":version["id"],"version_number":version["number"],"checked_rules":len(ruleset),"channel":draft["channel"],"findings":findings,"status":"issues_found" if findings else "no_issues_detected","disclaimer":"Only configured rules were checked; no comprehensive legal, factual or accessibility certification."}

@app.get("/runs/{run_id}")
def get_run(run_id:str):
    with db() as con:
        run=con.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
        if not run: raise HTTPException(404,"Run not found")
        return {**dict(run),"findings":rows(con.execute("SELECT * FROM findings WHERE run_id=? ORDER BY start",(run_id,)))}

@app.post("/drafts/{draft_id}/revisions",status_code=201)
def revise(draft_id:str,body:RevisionIn):
    with db() as con:
        _,v=latest(con,draft_id)
        new_id=ident()
        con.execute("INSERT INTO versions VALUES (?,?,?,?,?)",(new_id,draft_id,v["number"]+1,body.content,now()))
        return {"version_id":new_id,"number":v["number"]+1}

@app.post("/drafts/{draft_id}/reviews",status_code=201)
def review(draft_id:str,body:ReviewIn):
    with db() as con:
        _,v=latest(con,draft_id)
        # Approval requires testing this exact version and no findings.
        if body.decision=="approved":
            run=con.execute("SELECT id FROM runs WHERE version_id=? ORDER BY created_at DESC LIMIT 1",(v["id"],)).fetchone()
            if not run: raise HTTPException(409,"Run tests on the current version before approval")
            count=con.execute("SELECT COUNT(*) AS n FROM findings WHERE run_id=?",(run["id"],)).fetchone()["n"]
            if count: raise HTTPException(409,"Unresolved findings: correct and retest before approval")
        record={"id":ident(),"draft_id":draft_id,"version_id":v["id"],"decision":body.decision,"reviewer":body.reviewer,"comment":body.comment,"created_at":now()}
        con.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?)",tuple(record.values()))
        return record


# --- Brand knowledge intake and optional AI analysis (Round 2 extension) ---
class AIAnalysisIn(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    channel: Literal["social", "email", "website", "general"] = "general"
    send_source_excerpts: bool = False

@app.get("/ai/status")
def ai_status():
    return {"enabled": enabled(), "provider": "Google Gemini" if enabled() else None,
            "model": os.getenv("GLITCHLAB_AI_MODEL", "gemini-2.5-flash") if enabled() else None,
            "privacy_notice": "When used, draft text, active rules, and optionally uploaded source excerpts are sent to the configured external AI provider."}

@app.post("/ai/analyze")
def ai_analyze(body: AIAnalysisIn):
    if not enabled():
        raise HTTPException(503, "AI not configured on backend. Set GEMINI_API_KEY.")
    with db() as con:
        rules = [{k: r[k] for k in ("code", "category", "title", "explanation", "source")}
                 for r in applicable_rules(con, body.channel)]
        sources = rows(con.execute("SELECT filename, substr(content,1,2200) AS excerpt FROM sources ORDER BY created_at DESC LIMIT 6")) if body.send_source_excerpts else []
    try:
        return assess(body.content, body.channel, rules, sources)
    except AIUnavailable as exc:
        raise HTTPException(502, str(exc))

@app.post("/sources/import", status_code=201)
async def import_source(file: UploadFile = File(...)):
    name = (file.filename or 'untitled')[:180]
    ext = Path(name).suffix.lower()
    if ext not in ('.pdf', '.txt'):
        raise HTTPException(415, 'Only selectable-text PDF and TXT are supported')
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, 'Upload exceeds 2 MB')
    if ext == '.pdf':
        if not raw.startswith(b'%PDF-'):
            raise HTTPException(422, 'Invalid PDF signature')
        try:
            import fitz
            with fitz.open(stream=raw, filetype='pdf') as document:
                if document.page_count > 30:
                    raise HTTPException(413, 'PDF exceeds 30 pages')
                content = '\n'.join(page.get_text('text') for page in document)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, 'Could not parse PDF')
    else:
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise HTTPException(422, 'TXT must be UTF-8')
    content = content.strip()[:60000]
    if not content:
        raise HTTPException(422, 'No selectable text found; scanned PDFs are not supported')
    uid = ident()
    with db() as con:
        con.execute('INSERT INTO sources VALUES (?,?,?,?,?)', (uid, name, ext[1:], content, now()))
    return {'id':uid,'filename':name,'characters':len(content),'kind':ext[1:],
            'status':'imported_unapproved', 'message':'Source imported. Create or approve policy rules manually; importing does not activate any rule.'}

@app.get('/sources')
def list_sources():
    with db() as con:
        return rows(con.execute('SELECT id,filename,kind,length(content) AS characters,created_at FROM sources ORDER BY created_at DESC'))

@app.get('/sources/{source_id}')
def get_source(source_id: str):
    with db() as con:
        item = con.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Source not found')
        return dict(item)

@app.post('/sources/{source_id}/suggest-rules')
def suggest_source_rules(source_id: str):
    if not enabled():
        raise HTTPException(503, 'AI not configured on backend. Set GEMINI_API_KEY.')
    with db() as con:
        item = con.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Source not found')
    try:
        return propose_rules(item['filename'], item['content'])
    except AIUnavailable as exc:
        raise HTTPException(502, str(exc))


# --- Round 2 Governance Lab: exploratory policy tools; no draft mutations ---


# Advisory sentence rewrite: does not persist a new version or change approval.
class SmartPatchIn(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    channel: Literal["social", "email", "website", "general"] = "general"
    source_ids: list[str] = Field(default_factory=list, max_length=3)

@app.post("/ai/smart-patch")
def smart_patch(body: SmartPatchIn):
    if not enabled():
        raise HTTPException(503, "AI not configured on backend")
    with db() as con:
        active_rules = applicable_rules(con, body.channel)
        refs = []
        for source_id in dict.fromkeys(body.source_ids):
            item = con.execute("SELECT id,filename,content FROM sources WHERE id=?", (source_id,)).fetchone()
            if item is None:
                raise HTTPException(422, "Selected reference source was not found")
            refs.append(dict(item))
    try:
        return preview_smart_patch(body.content, body.channel, active_rules, refs)
    except AIUnavailable as exc:
        raise HTTPException(502, str(exc))


# Aggregate analytics from stored demonstration data. No invented figures.
@app.get("/insights")
def insights():
    with db() as con:
        counts = {
            "drafts": con.execute("SELECT COUNT(*) FROM drafts").fetchone()[0],
            "versions": con.execute("SELECT COUNT(*) FROM versions").fetchone()[0],
            "runs": con.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "findings": con.execute("SELECT COUNT(*) FROM findings").fetchone()[0],
            "approvals": con.execute("SELECT COUNT(*) FROM reviews WHERE decision='approved'").fetchone()[0],
            "change_requests": con.execute("SELECT COUNT(*) FROM reviews WHERE decision='changes_requested'").fetchone()[0],
        }
        by_rule = rows(con.execute("""SELECT f.rule_code AS code, f.title AS title,
                    COUNT(*) AS count FROM findings f GROUP BY f.rule_code,f.title
                    ORDER BY count DESC, f.rule_code LIMIT 12"""))
        by_category = rows(con.execute("""SELECT f.category AS category, COUNT(*) AS count
                    FROM findings f GROUP BY f.category ORDER BY count DESC"""))
        recent_runs = rows(con.execute("""SELECT r.id, d.title AS draft_title,
                    r.created_at, COUNT(f.id) AS findings
                    FROM runs r JOIN drafts d ON d.id=r.draft_id
                    LEFT JOIN findings f ON f.run_id=r.id
                    GROUP BY r.id ORDER BY r.created_at DESC LIMIT 8"""))
        return {"counts": counts, "by_rule": by_rule, "by_category": by_category,
                "recent_runs": recent_runs,
                "disclaimer": "Counts reflect stored demo activity, not distinct violations or verified compliance."}


# Governance Lab: exploratory tools with explicitly scoped, non-writing operations.
from governance_lab import install as install_governance_lab
app.include_router(install_governance_lab(db, applicable_rules))
