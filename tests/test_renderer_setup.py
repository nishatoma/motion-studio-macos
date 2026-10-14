"""Docker connection and preparation regressions; native Windows smoke is separate."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import code_motion_setup as setup
import render_runtime as runtime
import windows_support as ws

CONNECTION={'command':['docker','--context','desktop-linux'],'env':dict(os.environ),'installed':True,'running':True,'linux':True,'connection':'desktop-linux','details':'','message':'Docker connected'}

class RuntimeTest(unittest.TestCase):
    def test_stale_docker_host_uses_verified_local_desktop_without_global_switch(self):
        responses=[(1,'','cannot connect stale host'),(0,'npipe:////./pipe/dockerDesktopLinuxEngine',''),(0,'linux','')]
        with patch('render_runtime.platform.system',return_value='Windows'),patch('windows_support.tool_binary',return_value='docker.exe'),patch.dict(os.environ,{'DOCKER_HOST':'tcp://127.0.0.1:1','DOCKER_TLS_VERIFY':'1'}),patch('render_runtime.probe',side_effect=responses) as probe:
            value=runtime.docker_connection();self.assertTrue(value['linux']);self.assertEqual(value['command'],['docker.exe','--context','desktop-linux']);self.assertNotIn('DOCKER_HOST',value['env']);self.assertNotIn('DOCKER_TLS_VERIFY',value['env']);self.assertEqual(os.environ['DOCKER_HOST'],'tcp://127.0.0.1:1')
        self.assertFalse(any('use' in call.args[0] for call in probe.call_args_list))
    def test_remote_fallback_is_never_selected(self):
        with patch('render_runtime.platform.system',return_value='Windows'),patch('windows_support.tool_binary',return_value='docker'),patch('render_runtime.probe',side_effect=[(1,'','denied'),(0,'ssh://unrelated',''),(0,'tcp://unrelated:2375','')]) as probe:
            value=runtime.docker_connection();self.assertFalse(value['linux']);self.assertIn('denied',value['details']);self.assertIn('could not connect',value['message']);self.assertEqual(probe.call_count,3)
    def test_new_windows_install_locations(self):
        with tempfile.TemporaryDirectory() as tmp,patch('windows_support.platform.system',return_value='Windows'),patch('windows_support.shutil.which',return_value=None),patch.dict(os.environ,{'LOCALAPPDATA':tmp,'PROGRAMFILES':tmp}):
            root=Path(tmp)
            for rel in ['Programs/DockerDesktop/resources/bin/docker.exe','Microsoft/WinGet/Packages/Gyan.FFmpeg_x64/ffmpeg/bin/ffprobe.exe']:
                file=root/rel;file.parent.mkdir(parents=True);file.touch()
            self.assertEqual(ws.tool_binary('docker'),str(root/'Programs/DockerDesktop/resources/bin/docker.exe'));self.assertTrue(ws.tool_binary('ffprobe').endswith('ffprobe.exe'))
    def test_probe_timeout_is_diagnostic(self):
        with patch('render_runtime.subprocess.run',side_effect=subprocess.TimeoutExpired('docker',8)):
            code,_,error=runtime.probe(['docker'],{});self.assertEqual(code,1);self.assertIn('eight seconds',error)

class PreparationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.events=[]
    def test_ready_renderer_skips_installs_and_builds(self):
        with patch('render_runtime.docker_connection',return_value=CONNECTION),patch('render_runtime.renderer_status',return_value=(True,'')),patch('codex_provider.command',return_value=['codex']),patch('code_motion_setup.run_step') as step:
            setup.prepare(self.root,self.events.append);step.assert_not_called()
        self.assertEqual(self.events[-1]['progress'],1)
    def test_build_and_verify_share_the_selected_connection(self):
        with patch('render_runtime.docker_connection',return_value=CONNECTION),patch('render_runtime.renderer_status',side_effect=[(False,'missing'),(True,'')]),patch('codex_provider.command',return_value=['codex']),patch('code_motion_setup.run_step') as step:
            setup.prepare(self.root,self.events.append)
        self.assertEqual(step.call_args.args[0][:4],['docker','--context','desktop-linux','build']);self.assertEqual(step.call_args.args[2],CONNECTION['env'])
    def test_api_and_ollama_do_not_require_host_node_or_codex_for_docker_build(self):
        with patch('render_runtime.docker_connection',return_value=CONNECTION),patch('render_runtime.renderer_status',side_effect=[(False,'missing'),(True,'')]),patch('codex_provider.command',side_effect=ValueError('missing')),patch('windows_support.tool_binary',return_value=None),patch('code_motion_setup.run_step') as step:
            setup.prepare(self.root,self.events.append,install_codex=False)
        self.assertEqual(step.call_count,1);self.assertIn('build',step.call_args.args[0])
    def test_node_check_and_npm_do_not_use_inline_code_or_batch_shell(self):
        node=self.root/('node.exe' if os.name=='nt' else 'node');cli=self.root/'node_modules/npm/bin/npm-cli.js';cli.parent.mkdir(parents=True);cli.touch()
        with patch('render_runtime.docker_connection',return_value=CONNECTION),patch('render_runtime.renderer_status',return_value=(True,'')),patch('codex_provider.command',side_effect=ValueError('missing')),patch('windows_support.tool_binary',return_value=str(node)),patch('code_motion_setup.subprocess.run',return_value=subprocess.CompletedProcess([],0,'v22.20.0\n','')) as version,patch('code_motion_setup.run_step') as step:
            setup.prepare(self.root,self.events.append)
        self.assertEqual(version.call_args.args[0],[str(node),'--version']);self.assertEqual(step.call_args_list[0].args[0][:3],[str(node),str(cli),'ci']);self.assertEqual(step.call_count,2)
    def test_homebrew_npm_entry_does_not_depend_on_env_node_path(self):
        node=self.root/'brew/bin/node';cli=self.root/'brew/libexec/lib/node_modules/npm/bin/npm-cli.js';cli.parent.mkdir(parents=True);cli.touch()
        self.assertEqual(setup.npm_command(str(node)),[str(node),str(cli)])
    def test_old_node_reports_node_not_docker(self):
        with patch('render_runtime.docker_connection',return_value=CONNECTION),patch('render_runtime.renderer_status',return_value=(False,'')),patch('codex_provider.command',side_effect=ValueError('missing')),patch('windows_support.tool_binary',return_value='node'),patch('code_motion_setup.subprocess.run',return_value=subprocess.CompletedProcess([],0,'v18.0.0','')),self.assertRaisesRegex(setup.SetupError,'Docker is already connected'):
            setup.prepare(self.root,self.events.append)
    def test_native_stderr_is_progress_and_failures_preserve_stage(self):
        setup.run_step([sys.executable,'-c','import sys; print("normal build progress",file=sys.stderr)'],self.root,dict(os.environ),'Building animation renderer',self.events.append,5,None)
        self.assertTrue(any('normal build progress' in v.get('log','') for v in self.events))
        with self.assertRaisesRegex(setup.SetupError,'Installing.*failed.*exit 7'):
            setup.run_step([sys.executable,'-c','import sys; print("network download failed",file=sys.stderr);sys.exit(7)'],self.root,dict(os.environ),'Installing dependencies',self.events.append,5,None)
    def test_cancel_and_timeout_stop_the_native_child(self):
        cancel=threading.Event();timer=threading.Timer(.2,cancel.set);timer.start()
        with self.assertRaisesRegex(setup.SetupError,'cancelled'):
            setup.run_step([sys.executable,'-c','import time;time.sleep(20)'],self.root,dict(os.environ),'Building',self.events.append,5,cancel)
        timer.join()
        with self.assertRaisesRegex(setup.SetupError,'timed out'):
            setup.run_step([sys.executable,'-c','import time;time.sleep(20)'],self.root,dict(os.environ),'Building',self.events.append,.2,None)

if __name__=='__main__':unittest.main()
