# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from wmrm.benchmarks.mask_refinement_timing import (
    FAILURE_REASONS,
    PROTOCOL_ID,
    WORKFLOWS,
    MaskRefinementTimingError,
    _load_and_validate_session,
    _load_json,
    _sha256,
    _validate_result_header,
    create_result_template,
)

LOOPBACK_HOST = "127.0.0.1"
MAX_CORRECTION_SECONDS = 3_600.0
MAX_EDIT_ACTIONS = 10_000


class TrialSubmission(BaseModel):
    status: str
    correction_seconds: float = Field(ge=0, le=MAX_CORRECTION_SECONDS)
    edit_actions: int = Field(ge=0, le=MAX_EDIT_ACTIONS)
    failure_reason: str | None = Field(default=None, max_length=500)


class TimingSessionStore:
    def __init__(
        self,
        *,
        session_path: Path,
        results_path: Path,
        manifest_path: Path,
        refined_predictions_path: Path,
    ) -> None:
        self.session_path = session_path.resolve()
        self.results_path = results_path.resolve()
        self.manifest_path = manifest_path.resolve()
        self.refined_predictions_path = refined_predictions_path.resolve()
        self.session = _load_and_validate_session(self.session_path)
        self._verify_bound_inputs()
        self.tasks = self._validated_tasks()
        self.task_map = {task["task_id"]: task for task in self.tasks}
        self.workflow_labels = self._workflow_labels()
        self.lock = threading.Lock()
        self.active_task_id: str | None = None
        self.active_started_at: float | None = None
        if not self.results_path.exists():
            create_result_template(self.session_path, output=self.results_path)
        self._load_results()

    def state(self) -> dict[str, Any]:
        with self.lock:
            results = self._load_results()
            completed = {
                row["task_id"] for row in results["trials"] if row.get("status") is not None
            }
            pending = next((task for task in self.tasks if task["task_id"] not in completed), None)
            if pending is None:
                self.active_task_id = None
                self.active_started_at = None
                return {
                    "protocol_id": PROTOCOL_ID,
                    "participant_id": self.session["participant_id"],
                    "completed": len(completed),
                    "total": len(self.tasks),
                    "finished": True,
                    "task": None,
                }
            if self.active_task_id != pending["task_id"]:
                self.active_task_id = pending["task_id"]
                self.active_started_at = None
            return {
                "protocol_id": PROTOCOL_ID,
                "participant_id": self.session["participant_id"],
                "completed": len(completed),
                "total": len(self.tasks),
                "finished": False,
                "task": self._public_task(pending),
            }

    def start(self, task_id: str) -> dict[str, bool]:
        with self.lock:
            if self.active_task_id != task_id:
                raise HTTPException(status_code=409, detail="Only the active task may be started.")
            if self.active_started_at is None:
                self.active_started_at = time.monotonic()
            return {"started": True}

    def submit(self, task_id: str, submission: TrialSubmission) -> dict[str, Any]:
        with self.lock:
            results = self._load_results()
            pending = next(
                (row for row in results["trials"] if row.get("status") is None), None
            )
            if pending is None:
                raise HTTPException(status_code=409, detail="Timing session is already complete.")
            if pending["task_id"] != task_id or self.active_task_id != task_id:
                raise HTTPException(status_code=409, detail="Only the active task may be submitted.")
            if self.active_started_at is None:
                raise HTTPException(status_code=409, detail="Active task timer is unavailable.")
            if submission.status not in {"completed", "failed"}:
                raise HTTPException(status_code=422, detail="Invalid trial status.")
            reason = (submission.failure_reason or "").strip()
            if submission.status == "failed" and not reason:
                raise HTTPException(status_code=422, detail="Failed trials require a reason.")
            if submission.status == "failed" and reason not in FAILURE_REASONS:
                raise HTTPException(status_code=422, detail="Unsupported failure reason.")
            if submission.status == "completed" and reason:
                raise HTTPException(status_code=422, detail="Completed trials cannot have a reason.")
            total_seconds = max(0.001, time.monotonic() - self.active_started_at)
            if submission.correction_seconds > total_seconds + 0.05:
                raise HTTPException(
                    status_code=422,
                    detail="Correction time cannot exceed total task time.",
                )
            pending.update(
                {
                    "total_seconds": round(total_seconds, 3),
                    "correction_seconds": round(submission.correction_seconds, 3),
                    "status": submission.status,
                    "failure_reason": reason or None,
                    "edit_actions": submission.edit_actions,
                }
            )
            self._write_results(results)
            self.active_task_id = None
            self.active_started_at = None
        return self.state()

    def image_path(self, task_id: str) -> Path:
        task = self._task(task_id)
        path = (self.manifest_path.parent / task["image_file"]).resolve()
        self._verify_asset(path, task["image_sha256"], self.manifest_path.parent)
        return path

    def mask_path(self, task_id: str) -> Path:
        task = self._task(task_id)
        path = (
            self.refined_predictions_path.parent / task["refined_mask_file"]
        ).resolve()
        self._verify_asset(
            path,
            task["refined_mask_sha256"],
            self.refined_predictions_path.parent,
        )
        return path

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self.task_map.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Unknown timing task.")
        return task

    def _verify_bound_inputs(self) -> None:
        if _sha256(self.manifest_path) != self.session["corpus_sha256"]:
            raise MaskRefinementTimingError("Timing session corpus digest mismatch.")
        if _sha256(self.refined_predictions_path) != self.session[
            "refined_predictions_sha256"
        ]:
            raise MaskRefinementTimingError("Timing session prediction digest mismatch.")

    def _validated_tasks(self) -> list[dict[str, Any]]:
        tasks = self.session["tasks"]
        for task in tasks:
            if task.get("workflow") not in WORKFLOWS:
                raise MaskRefinementTimingError("Timing session contains an invalid workflow.")
            width = task.get("width")
            height = task.get("height")
            if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
                raise MaskRefinementTimingError("Timing task dimensions are invalid.")
            self.image_path_from_task(task)
            self.mask_path_from_task(task)
        return tasks

    def image_path_from_task(self, task: dict[str, Any]) -> Path:
        path = (self.manifest_path.parent / task["image_file"]).resolve()
        self._verify_asset(path, task["image_sha256"], self.manifest_path.parent)
        return path

    def mask_path_from_task(self, task: dict[str, Any]) -> Path:
        path = (
            self.refined_predictions_path.parent / task["refined_mask_file"]
        ).resolve()
        self._verify_asset(
            path,
            task["refined_mask_sha256"],
            self.refined_predictions_path.parent,
        )
        return path

    @staticmethod
    def _verify_asset(path: Path, expected: str, root: Path) -> None:
        if path != root and root not in path.parents:
            raise MaskRefinementTimingError("Timing asset leaves its allowed root.")
        if not path.is_file() or _sha256(path) != expected:
            raise MaskRefinementTimingError("Timing asset integrity check failed.")

    def _workflow_labels(self) -> dict[str, str]:
        labels = ("A", "B", "C")
        offset = int(self.session["participant_id"][:8], 16) % len(labels)
        rotated = labels[offset:] + labels[:offset]
        return dict(zip(WORKFLOWS, rotated, strict=True))

    def _public_task(self, task: dict[str, Any]) -> dict[str, Any]:
        workflow = task["workflow"]
        initialization: dict[str, Any] = {"kind": "empty"}
        if workflow == "box":
            initialization = {"kind": "rectangle", "box": task["candidate_box"]}
        elif workflow == "refined":
            initialization = {
                "kind": "bitmap",
                "mask_url": f"/api/tasks/{task['task_id']}/mask",
            }
        return {
            "task_id": task["task_id"],
            "method_label": self.workflow_labels[workflow],
            "width": task["width"],
            "height": task["height"],
            "image_url": f"/api/tasks/{task['task_id']}/image",
            "initialization": initialization,
        }

    def _load_results(self) -> dict[str, Any]:
        result = _load_json(self.results_path)
        _validate_result_header(self.session, result)
        trials = result.get("trials")
        if not isinstance(trials, list) or len(trials) != len(self.tasks):
            raise MaskRefinementTimingError("Timing result template does not match the session.")
        expected = [task["task_id"] for task in self.tasks]
        actual = [row.get("task_id") for row in trials if isinstance(row, dict)]
        if actual != expected:
            raise MaskRefinementTimingError("Timing results changed task order or identity.")
        return result

    def _write_results(self, result: dict[str, Any]) -> None:
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.results_path.parent,
            prefix=f".{self.results_path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            temporary.chmod(0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.results_path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)


def create_timing_ui_app(store: TimingSessionStore) -> FastAPI:
    app = FastAPI(
        title="Watermark mask timing study",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return TIMING_UI_HTML

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return store.state()

    @app.get("/api/tasks/{task_id}/image")
    def image(task_id: str):
        return FileResponse(store.image_path(task_id), media_type="image/png")

    @app.get("/api/tasks/{task_id}/mask")
    def mask(task_id: str):
        task = store._task(task_id)
        if task["workflow"] != "refined":
            raise HTTPException(status_code=404, detail="This task has no bitmap suggestion.")
        return FileResponse(store.mask_path(task_id), media_type="image/png")

    @app.post("/api/tasks/{task_id}/complete")
    def complete(task_id: str, submission: TrialSubmission) -> dict[str, Any]:
        return store.submit(task_id, submission)

    @app.post("/api/tasks/{task_id}/start")
    def start(task_id: str) -> dict[str, bool]:
        return store.start(task_id)

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local blind mask timing interface.")
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--refined-predictions", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8776)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    try:
        store = TimingSessionStore(
            session_path=args.session,
            results_path=args.results,
            manifest_path=args.manifest,
            refined_predictions_path=args.refined_predictions,
        )
    except MaskRefinementTimingError as error:
        raise SystemExit(str(error)) from error
    url = f"http://{LOOPBACK_HOST}:{args.port}/"
    print(f"Mask refinement timing study: {url}")
    uvicorn.run(create_timing_ui_app(store), host=LOOPBACK_HOST, port=args.port, access_log=False)
    return 0


TIMING_UI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>蒙版操作计时</title>
  <style>
    :root { color-scheme: light; --ink:#17221c; --muted:#5a675f; --line:#cad2cb; --paper:#fbfcf8; --green:#1f6147; --red:#be432f; }
    * { box-sizing:border-box } body { margin:0; color:var(--ink); background:#edf0e9; font:16px/1.55 system-ui,-apple-system,sans-serif }
    main { width:min(1120px,calc(100% - 32px)); margin:24px auto 48px }
    header { display:flex; justify-content:space-between; gap:24px; align-items:flex-start; margin-bottom:18px }
    h1 { margin:0 0 6px; font-size:clamp(1.55rem,4vw,2.35rem) } h2 { margin:0; font-size:1.1rem }
    p { margin:6px 0 } .muted { color:var(--muted) } .panel { border:1px solid var(--line); border-radius:18px; background:var(--paper); padding:20px }
    .progress { min-width:180px; text-align:right; font-variant-numeric:tabular-nums } .progress strong { display:block; font-size:1.25rem }
    .task-head,.toolbar,.actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px }
    .task-head { justify-content:space-between; margin-bottom:14px } .method { padding:6px 12px; border-radius:999px; color:#fff; background:var(--green); font-weight:750 }
    button,input,select { font:inherit } button { border:0; border-radius:10px; padding:10px 15px; cursor:pointer; font-weight:700 }
    button:focus-visible,input:focus-visible,select:focus-visible { outline:3px solid rgba(31,97,71,.3); outline-offset:2px }
    .tool { border:1px solid var(--line); background:#fff; color:var(--green) } .tool[aria-pressed="true"] { color:#fff; background:var(--green); border-color:var(--green) }
    .primary { color:#fff; background:var(--green) } .danger { color:#fff; background:var(--red) } button:disabled { opacity:.45; cursor:not-allowed }
    .toolbar { margin-bottom:12px } .toolbar label { display:flex; align-items:center; gap:8px; color:var(--muted) }
    .canvas-wrap { overflow:hidden; border:1px solid var(--line); border-radius:14px; background:#dfe4dc; touch-action:none }
    canvas { display:block; width:100%; height:auto; cursor:crosshair } .actions { justify-content:space-between; margin-top:14px }
    .timers { display:flex; gap:18px; color:var(--muted); font-variant-numeric:tabular-nums }
    .failure { display:grid; grid-template-columns:1fr auto; gap:10px; width:100%; margin-top:12px }
    select { min-height:46px; border:1px solid var(--line); border-radius:10px; padding:10px; background:#fff }
    .notice { margin-top:12px; padding:10px 12px; border-radius:10px; background:#fff2d7; color:#74480a }
    .error { background:#fde9e5; color:#842f22 } [hidden] { display:none!important }
    @media (max-width:700px) { header,.actions { align-items:stretch; flex-direction:column } .progress { text-align:left } .failure { grid-template-columns:1fr } }
  </style>
</head>
<body><main>
  <header><div><h1>蒙版操作计时</h1><p class="muted">请把红色区域调整到完整覆盖水印，同时尽量保留正常画面。</p></div><div class="progress"><span>匿名会话</span><strong id="participant">—</strong><span id="progress">正在载入…</span></div></header>
  <section id="ready" class="panel" hidden>
    <h2>准备开始下一项任务</h2>
    <p>确认已经阅读说明并可以连续操作后，再点击开始。点击后才会加载任务并启动总计时。</p>
    <p class="muted">每项任务只根据画面判断；不要查看文件、开发工具或之前的结果。</p>
    <button id="begin" class="primary">开始任务</button>
  </section>
  <section id="study" class="panel" hidden>
    <div class="task-head"><div><h2>当前任务</h2><p class="muted">只根据画面判断，不查看文件或开发工具。</p></div><span id="method" class="method">方案 —</span></div>
    <div class="toolbar" role="toolbar" aria-label="蒙版工具">
      <button id="add" class="tool" aria-pressed="true">添加蒙版</button><button id="erase" class="tool" aria-pressed="false">擦除蒙版</button>
      <label>笔刷 <input id="size" type="range" min="4" max="64" value="20"> <span id="sizeValue">20 px</span></label>
      <button id="undo" class="tool" disabled>撤销</button><button id="reset" class="tool">恢复初始蒙版</button>
    </div>
    <div class="canvas-wrap"><canvas id="canvas" aria-label="水印蒙版编辑画布"></canvas></div>
    <div class="actions"><div class="timers"><span>总耗时 <strong id="total">0.0s</strong></span><span>修正耗时 <strong id="correction">0.0s</strong></span></div><button id="complete" class="primary" disabled>确认蒙版并继续</button></div>
    <div class="failure"><select id="reason" aria-label="失败原因"><option value="">仅在无法完成时选择失败原因</option><option value="mask_not_usable">无法得到可用蒙版</option><option value="editor_problem">编辑器操作异常</option><option value="time_limit">操作时间过长</option><option value="other">其他原因</option></select><button id="fail" class="danger">标记失败并继续</button></div>
    <p id="message" class="notice" hidden></p>
  </section>
  <section id="finished" class="panel" hidden><h2>本次计时已完成</h2><p>结果已经保存在本机。请通知实验操作员进行匿名审计。</p></section>
</main>
<script>
const $ = id => document.getElementById(id)
const canvas=$('canvas'), ctx=canvas.getContext('2d',{willReadFrequently:true}), state={pendingTask:null,task:null,image:null,mask:null,initial:null,tool:'add',size:20,drawing:false,last:null,history:[],actions:0,taskStart:0,correctionMs:0,strokeStart:0,timer:null,submitting:false}
async function api(url,options){const response=await fetch(url,options);if(!response.ok){let detail='请求失败';try{detail=(await response.json()).detail||detail}catch{}throw new Error(detail)}return response.json()}
function setMessage(text,error=false){$('message').hidden=!text;$('message').textContent=text;$('message').className=`notice${error?' error':''}`}
async function loadState(){setMessage('');clearInterval(state.timer);state.task=null;state.taskStart=0;const data=await api('/api/state');$('participant').textContent=data.participant_id;$('progress').textContent=`${data.completed} / ${data.total}`;$('study').hidden=true;if(data.finished){state.pendingTask=null;$('ready').hidden=true;$('finished').hidden=false;return}state.pendingTask=data.task;$('ready').hidden=false;$('finished').hidden=true}
async function loadTask(task){state.pendingTask=null;state.task=task;state.history=[];state.actions=0;state.correctionMs=0;selectTool('add');$('undo').disabled=true;$('method').textContent=`方案 ${task.method_label}`;$('reason').value='';const image=new Image();image.src=task.image_url;await image.decode();state.image=image;canvas.width=task.width;canvas.height=task.height;state.mask=new Uint8Array(task.width*task.height);if(task.initialization.kind==='rectangle'){const b=task.initialization.box;for(let y=Math.floor(b.y0);y<Math.ceil(b.y1);y++)for(let x=Math.floor(b.x0);x<Math.ceil(b.x1);x++)state.mask[y*task.width+x]=1}else if(task.initialization.kind==='bitmap'){const mask=new Image();mask.src=task.initialization.mask_url;await mask.decode();const off=document.createElement('canvas');off.width=task.width;off.height=task.height;const ox=off.getContext('2d',{willReadFrequently:true});ox.drawImage(mask,0,0);const pixels=ox.getImageData(0,0,task.width,task.height).data;for(let i=0;i<state.mask.length;i++)state.mask[i]=pixels[i*4]>127?1:0}state.initial=state.mask.slice();render();updateComplete();$('ready').hidden=true;$('study').hidden=false;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));await api(`/api/tasks/${task.task_id}/start`,{method:'POST'});state.taskStart=performance.now();state.timer=setInterval(updateTimers,100)}
function render(){ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(state.image,0,0,canvas.width,canvas.height);const layer=document.createElement('canvas');layer.width=canvas.width;layer.height=canvas.height;const layerContext=layer.getContext('2d');const overlay=layerContext.createImageData(canvas.width,canvas.height);for(let i=0;i<state.mask.length;i++)if(state.mask[i]){overlay.data[i*4]=205;overlay.data[i*4+1]=50;overlay.data[i*4+2]=34;overlay.data[i*4+3]=112}layerContext.putImageData(overlay,0,0);ctx.drawImage(layer,0,0)}
function point(event){const r=canvas.getBoundingClientRect();return{x:(event.clientX-r.left)/r.width*canvas.width,y:(event.clientY-r.top)/r.height*canvas.height}}
function paint(p){const radius=state.size/2,x0=Math.max(0,Math.floor(p.x-radius)),x1=Math.min(canvas.width,Math.ceil(p.x+radius)),y0=Math.max(0,Math.floor(p.y-radius)),y1=Math.min(canvas.height,Math.ceil(p.y+radius));for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)if((x-p.x)**2+(y-p.y)**2<=radius**2)state.mask[y*canvas.width+x]=state.tool==='add'?1:0}
function interpolate(a,b){const d=Math.hypot(b.x-a.x,b.y-a.y),n=Math.max(1,Math.ceil(d/Math.max(2,state.size*.35)));for(let i=1;i<=n;i++)paint({x:a.x+(b.x-a.x)*i/n,y:a.y+(b.y-a.y)*i/n})}
canvas.addEventListener('pointerdown',e=>{if(state.submitting)return;state.history.push(state.mask.slice());if(state.history.length>20)state.history.shift();state.drawing=true;state.strokeStart=performance.now();state.last=point(e);paint(state.last);canvas.setPointerCapture(e.pointerId);render();updateComplete()})
canvas.addEventListener('pointermove',e=>{if(!state.drawing)return;const p=point(e);interpolate(state.last,p);state.last=p;render();updateComplete()})
function endStroke(e){if(!state.drawing)return;state.drawing=false;state.correctionMs+=performance.now()-state.strokeStart;state.actions++;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);$('undo').disabled=false;updateTimers()}
canvas.addEventListener('pointerup',endStroke);canvas.addEventListener('pointercancel',endStroke)
function selectTool(tool){state.tool=tool;$('add').setAttribute('aria-pressed',String(tool==='add'));$('erase').setAttribute('aria-pressed',String(tool==='erase'))}
$('add').onclick=()=>selectTool('add');$('erase').onclick=()=>selectTool('erase');$('size').oninput=e=>{state.size=Number(e.target.value);$('sizeValue').textContent=`${state.size} px`}
$('undo').onclick=()=>{const previous=state.history.pop();if(!previous)return;state.mask=previous;state.actions++;render();$('undo').disabled=!state.history.length;updateComplete()}
$('reset').onclick=()=>{state.history.push(state.mask.slice());state.mask=state.initial.slice();state.actions++;render();$('undo').disabled=false;updateComplete()}
function maskPixels(){let count=0;for(const value of state.mask)count+=value;return count}
function updateComplete(){$('complete').disabled=!state.task||maskPixels()===0||state.submitting}
function updateTimers(){if(!state.taskStart)return;$('total').textContent=`${((performance.now()-state.taskStart)/1000).toFixed(1)}s`;$('correction').textContent=`${(state.correctionMs/1000).toFixed(1)}s`}
async function submit(status){if(state.submitting)return;const reason=$('reason').value.trim();if(status==='failed'&&!reason){setMessage('请填写无法完成的原因。',true);$('reason').focus();return}state.submitting=true;updateComplete();try{await api(`/api/tasks/${state.task.task_id}/complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,correction_seconds:state.correctionMs/1000,edit_actions:state.actions,failure_reason:status==='failed'?reason:null})});state.task=null;await loadState()}catch(error){setMessage(error.message,true)}finally{state.submitting=false;updateComplete()}}
$('begin').onclick=async()=>{if(!state.pendingTask)return;$('begin').disabled=true;$('begin').textContent='正在加载…';try{await loadTask(state.pendingTask)}catch(error){state.task=null;setMessage(error.message,true);await loadState()}finally{$('begin').disabled=false;$('begin').textContent='开始任务'}}
$('complete').onclick=()=>submit('completed');$('fail').onclick=()=>submit('failed');window.addEventListener('beforeunload',e=>{if(state.taskStart){e.preventDefault();e.returnValue=''}});loadState().catch(error=>setMessage(error.message,true))
</script></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
