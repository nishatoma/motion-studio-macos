"""One Docker connection for readiness, preparation, rendering and cleanup."""
from __future__ import annotations
import os
import platform
import subprocess
import windows_support

IMAGE = 'motion-studio-remotion:1'

def probe(args, env, timeout=8):
    try:
        result=subprocess.run(args,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        return result.returncode,result.stdout.strip(),result.stderr.strip()
    except subprocess.TimeoutExpired:return 1,'','Docker did not respond within eight seconds.'
    except OSError as exc:return 1,'',str(exc)

def docker_connection():
    binary=windows_support.tool_binary('docker')
    env=dict(os.environ)
    value={'command':[binary or 'docker'],'env':env,'installed':bool(binary),'running':False,'linux':False,'connection':'current Docker connection','details':''}
    if not binary:
        value['message']='Docker CLI was not found. Install Docker Desktop, then restart Motion Studio.';return value
    code,kind,error=probe([binary,'info','--format','{{.OSType}}'],env)
    value.update(running=code==0,linux=code==0 and kind=='linux',details=error[-1600:])
    if not value['linux'] and platform.system() in {'Windows','Darwin'}:
        # Try only verified local Desktop sockets/pipes. Never change the user's
        # global context or follow an unrelated SSH/TCP fallback.
        local_env={k:v for k,v in env.items() if k not in {'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'}}
        for context in ('desktop-linux','default'):
            found,endpoint,_=probe([binary,'context','inspect',context,'--format','{{.Endpoints.docker.Host}}'],local_env)
            if found or not endpoint.startswith(('npipe://','unix://')):continue
            command=[binary,'--context',context]
            code,kind,_=probe([*command,'info','--format','{{.OSType}}'],local_env)
            if code==0 and kind=='linux':
                value.update(command=command,env=local_env,running=True,linux=True,connection=context,details='');break
    if value['linux']:value['message']='Docker is connected and running Linux containers.'
    elif value['running']:value['message']='Docker is running Windows containers. In Docker Desktop, switch to Linux containers, then click Check renderer.'
    else:value['message']='Motion Studio could not connect to Docker. If Docker Desktop is already running, check the connection details below, then click Check renderer.'
    return value

def renderer_status(connection):
    if not connection['linux']:return False,''
    code,_,error=probe([*connection['command'],'image','inspect',IMAGE],connection['env'])
    return code==0,error[-1600:]
