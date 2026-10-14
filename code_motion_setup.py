"""Trusted cross-platform preparation; no model-authored install commands."""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import codex_provider
import render_runtime
import windows_support

class SetupError(ValueError):pass

def npm_command(node):
    # Invoke npm's JS entry with Node directly, including on Windows. No .cmd
    # shell, PowerShell inline JavaScript, quoting workaround or shell=True.
    directory=Path(node).resolve().parent
    for cli in [directory/'node_modules/npm/bin/npm-cli.js',directory.parent/'lib/node_modules/npm/bin/npm-cli.js',directory.parent/'libexec/lib/node_modules/npm/bin/npm-cli.js']:
        if cli.is_file():return [node,str(cli)]
    npm=windows_support.tool_binary('npm')
    if npm and Path(npm).resolve().suffix=='.js':return [node,str(Path(npm).resolve())]
    if npm and Path(npm).suffix.lower() not in {'.cmd','.bat','.ps1'}:return [npm]
    raise SetupError('Node.js is installed but npm was not found. Repair the Node.js 22+ installation, then try Prepare renderer again.')

def stop_process(process):
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10)
    else:os.killpg(process.pid,signal.SIGTERM)
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name!='nt':os.killpg(process.pid,signal.SIGKILL)
        else:process.kill()
        process.wait(timeout=5)

def run_step(args,root,env,stage,emit,timeout,cancel_event):
    if cancel_event and cancel_event.is_set():raise SetupError('Renderer preparation cancelled. You can retry Prepare renderer.')
    emit({'stage':stage,'message':stage,'progress':0})
    try:
        process=subprocess.Popen(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',**({'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}))
    except OSError as exc:raise SetupError(f'{stage} could not start: {exc}') from exc
    lines=queue.Queue();tail=[]
    def read():
        try:
            for line in process.stdout:lines.put(line)
        finally:lines.put(None)
    reader=threading.Thread(target=read,daemon=True);reader.start();deadline=time.monotonic()+timeout
    try:
        while True:
            if cancel_event and cancel_event.is_set():raise SetupError('Renderer preparation cancelled. You can retry Prepare renderer.')
            if time.monotonic()>deadline:raise SetupError(f'{stage} timed out after {timeout} seconds. Check the setup log and retry.')
            try:line=lines.get(timeout=.2)
            except queue.Empty:continue
            if line is None:break
            tail.append(line.strip());tail=tail[-12:];emit({'stage':stage,'message':stage,'log':line})
        if process.wait(timeout=5)!=0:
            detail='\n'.join(tail)[-3000:]
            raise SetupError(f'{stage} failed (exit {process.returncode}).\n{detail}')
    finally:
        stop_process(process);reader.join(timeout=2);process.stdout.close()

def prepare(root,emit,cancel_event=None,install_codex=True):
    root=Path(root).resolve()
    emit({'stage':'Checking Docker','message':'Checking the existing Docker connection…','progress':.05})
    runtime=render_runtime.docker_connection()
    if cancel_event and cancel_event.is_set():raise SetupError('Renderer preparation cancelled.')
    if not runtime['linux']:raise SetupError(runtime['message']+'\n'+runtime['details'])
    emit({'stage':'Docker connected','message':'Docker is already running. Checking the animation renderer…','progress':.1})
    image,_=render_runtime.renderer_status(runtime)
    try:codex_provider.command();codex_installed=True
    except ValueError:codex_installed=False
    if install_codex and not codex_installed:
        node=windows_support.tool_binary('node')
        if not node:raise SetupError('Install Node.js 22 or newer, then click Prepare renderer. Docker does not need reinstalling.')
        try:version=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
        except (OSError,subprocess.SubprocessError) as exc:raise SetupError('Node.js could not start. Repair Node.js 22+, then retry.') from exc
        match=re.fullmatch(r'v?(\d+)\.\d+\.\d+.*',version)
        if not match or int(match[1])<22:raise SetupError(f'Node.js 22+ is required for ChatGPT support; found {version}. Update Node.js, then retry. Docker is already connected.')
        npm=npm_command(node)
        run_step([*npm,'ci','--prefix',str(root/'code-motion')],root,runtime['env'],'Installing ChatGPT and editor dependencies',emit,900,cancel_event)
        run_step([*npm,'test','--prefix',str(root/'code-motion')],root,runtime['env'],'Checking animation dependencies',emit,120,cancel_event)
    if not image:
        emit({'stage':'Building renderer','message':'Preparing the animation renderer for first use. This can take several minutes; Docker is already connected.','progress':.35})
        run_step([*runtime['command'],'build','--progress=plain','-t',render_runtime.IMAGE,str(root/'code-motion')],root,runtime['env'],'Building animation renderer',emit,1800,cancel_event)
    emit({'stage':'Verifying renderer','message':'Checking the prepared renderer…','progress':.95})
    verified,details=render_runtime.renderer_status(runtime)
    if cancel_event and cancel_event.is_set():raise SetupError('Renderer preparation cancelled.')
    if not verified:raise SetupError('Docker is connected, but the renderer could not be verified.\n'+details)
    emit({'stage':'Ready','message':'Renderer ready. Generate your preview.','progress':1})

def main():
    def emit(value):print(json.dumps(value),flush=True)
    try:prepare(Path(__file__).resolve().parent,emit)
    except (SetupError,OSError,subprocess.SubprocessError) as exc:
        emit({'stage':'error','message':str(exc),'error':str(exc)});return 1
    return 0

if __name__=='__main__':sys.exit(main())
