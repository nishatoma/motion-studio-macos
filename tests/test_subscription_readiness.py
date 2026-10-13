"""Subscription transport and Windows readiness. Live login is deliberately not automated."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
import codex_provider as cp
import code_motion as cm
import windows_support as ws

class SubscriptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.provider=cp.Subscription(Path(self.tmp.name))
    def test_environment_excludes_api_and_inherited_codex_tokens(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret-api','CODEX_ACCESS_TOKEN':'secret-token','ANTHROPIC_API_KEY':'other-secret'}):env=cp.environment(self.provider.home)
        self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('CODEX_ACCESS_TOKEN',env);self.assertNotIn('ANTHROPIC_API_KEY',env);self.assertEqual(env['CODEX_HOME'],str(self.provider.home))
    def test_status_distinguishes_chatgpt_and_api_key_login(self):
        with patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.run',return_value=subprocess.CompletedProcess([],0,'','Logged in using ChatGPT')):self.assertTrue(self.provider.status()['signed_in'])
        with patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.run',return_value=subprocess.CompletedProcess([],0,'','Logged in using an API key')):self.assertFalse(self.provider.status()['signed_in'])
    def test_no_key_generation_uses_schema_images_and_disabled_tools(self):
        result={'source':'safe TSX','design_notes':'style','review_frames':[3]};calls=[]
        def spawn(args,**kwargs):
            calls.append((args,kwargs));Path(args[args.index('-o')+1]).write_text(json.dumps(result));p=MagicMock();p.poll.return_value=0;p.returncode=0;return p
        im=Image.new('RGB',(16,16));buffer=io.BytesIO();im.save(buffer,'JPEG');image='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
        with patch.object(self.provider,'status',return_value={'signed_in':True}),patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',side_effect=spawn),patch.dict(os.environ,{'OPENAI_API_KEY':'not-for-codex'}):
            self.assertEqual(self.provider.generate('','instructions','prompt',cm.SCENE_SCHEMA,[image]),result)
        args,kwargs=calls[0];self.assertIn('--ignore-user-config',args);self.assertIn('--ephemeral',args);self.assertIn('--output-schema',args);self.assertIn('--image',args);self.assertEqual(args[args.index('--sandbox')+1],'read-only');self.assertNotIn('--model',args)
        for feature in cp.DISABLED_FEATURES:self.assertIn(feature,args)
        self.assertNotIn('OPENAI_API_KEY',kwargs['env']);self.assertNotIn('not-for-codex',' '.join(args));self.assertNotIn('shell',kwargs)
    def test_codex_default_model_needs_no_api_key(self):
        with patch.dict(os.environ,{'CODEX_MODEL':''}):settings=cm.settings({'prompt':'Create a title','provider':'codex','model':''})
        self.assertEqual(settings['model'],'');self.assertEqual(settings['provider'],'codex')
    def test_selected_sol_model_is_forwarded_without_substitution(self):
        def spawn(args,**kwargs):
            self.assertEqual(args[args.index('--model')+1],'gpt-5.6-sol')
            Path(args[args.index('-o')+1]).write_text(json.dumps({'source':'tsx','design_notes':'test','review_frames':[]}))
            p=MagicMock();p.poll.return_value=0;p.returncode=0;return p
        with patch.object(self.provider,'status',return_value={'signed_in':True}),patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',side_effect=spawn):
            self.provider.generate('gpt-5.6-sol','instructions','prompt',cm.SCENE_SCHEMA)
    def test_sign_in_launch_failure_is_actionable(self):
        with patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',side_effect=OSError('missing executable')),self.assertRaisesRegex(ValueError,'restart Motion Studio'):
            self.provider.sign_in()
        self.assertEqual(self.provider.login_status()['status'],'error')
    def test_models_presets_account_cache_and_unavailable_catalog(self):
        with patch.object(self.provider,'status',return_value={'signed_in':False}),patch.object(self.provider,'_list_models') as discover:
            catalog=self.provider.models();self.assertEqual(catalog['source'],'presets');self.assertIn('gpt-5.6-sol',[m['id'] for m in catalog['models']]);discover.assert_not_called()
        models=[{'id':'account-model','name':'My account model'}]
        with patch.object(self.provider,'status',return_value={'signed_in':True}),patch.object(self.provider,'_list_models',return_value=models) as discover:
            self.assertEqual(self.provider.models()['models'],models);self.provider.models();discover.assert_called_once()
        self.provider.model_cache=None
        with patch.object(self.provider,'status',return_value={'signed_in':True}),patch.object(self.provider,'_list_models',side_effect=ValueError('unavailable')):
            catalog=self.provider.models();self.assertEqual(catalog['source'],'presets');self.assertIn('availability is checked',catalog['message'])
    def test_model_discovery_uses_stdio_private_profile_and_pagination(self):
        p=MagicMock();p.stdin=io.StringIO();p.poll.return_value=None
        data=[{'id':1,'result':{}},{'id':2,'result':{'data':[{'id':'record-1','model':'gpt-5.6-sol','displayName':'GPT-5.6 Sol'},{'model':'hidden','hidden':True},{'model':'invalid model'}],'nextCursor':'page-2'}},{'id':3,'result':{'data':[{'model':'gpt-6.1-sol','displayName':'GPT-6.1 Sol'},{'model':'gpt-5.6-sol','displayName':'GPT-5.6 Sol'}],'nextCursor':None}}]
        p.stdout=io.StringIO(''.join(json.dumps(m)+'\n' for m in data))
        requests=[];p.stdin.close=lambda:requests.extend(json.loads(line) for line in p.stdin.getvalue().splitlines())
        with patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',return_value=p) as spawn:
            self.assertEqual([m['id'] for m in self.provider._list_models()],['gpt-5.6-sol','gpt-6.1-sol'])
        args=spawn.call_args.args[0];self.assertEqual(args[:3],['codex','app-server','--stdio']);self.assertNotIn('--listen',args)
        self.assertEqual(spawn.call_args.kwargs['env']['CODEX_HOME'],str(self.provider.home));self.assertNotIn('OPENAI_API_KEY',spawn.call_args.kwargs['env'])
        self.assertEqual([r['method'] for r in requests],['initialize','initialized','model/list','model/list']);self.assertEqual(requests[-1]['params']['cursor'],'page-2');p.terminate.assert_called_once()
    def test_model_discovery_protocol_error_cleans_up_process(self):
        p=MagicMock();p.stdin=io.StringIO();p.stdout=io.StringIO('{"id":1,"error":{"message":"failed"}}\n');p.poll.return_value=None
        p.wait.side_effect=[subprocess.TimeoutExpired('codex',5),0]
        with patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',return_value=p),self.assertRaisesRegex(ValueError,'metadata request failed'):
            self.provider._list_models()
        p.terminate.assert_called_once();p.kill.assert_called_once()
    def test_codex_review_uses_same_subscription_not_responses_api(self):
        studio=cm.Studio(Path(self.tmp.name));id='a'*12;p=studio.projects/id;p.mkdir();(p/'frames').mkdir();studio.events[id]=threading.Event();(p/'job.json').write_text(json.dumps({'transparent':False}));Image.new('RGB',(20,20)).save(p/'frames/1.png')
        config={'provider':'codex','model':'','prompt':'title','style_direction':'dark','beats':[]}
        with patch.object(studio.subscription,'generate',return_value={'needs_revision':False,'feedback':['Readable']}) as gen,patch('code_motion.urllib.request.urlopen',side_effect=AssertionError('Must not use API')):
            self.assertFalse(studio.review(id,config)['needs_revision'])
        gen.assert_called_once()
    def test_missing_login_returns_actionable_error(self):
        with patch.object(self.provider,'status',return_value={'signed_in':False}),self.assertRaisesRegex(ValueError,'Sign in with ChatGPT'):self.provider.generate('','i','p',cm.SCENE_SCHEMA)
    def test_cli_failure_never_silently_uses_api(self):
        p=MagicMock();p.poll.return_value=1;p.returncode=1
        with patch.object(self.provider,'status',return_value={'signed_in':True}),patch('codex_provider.command',return_value=['codex']),patch('codex_provider.subprocess.Popen',return_value=p),self.assertRaisesRegex(ValueError,'No API fallback'):self.provider.generate('','i','p',cm.SCENE_SCHEMA)

class ReadinessTest(unittest.TestCase):
    def test_tools_resolve_after_windows_install_without_path_refresh(self):
        with tempfile.TemporaryDirectory() as tmp,patch('windows_support.platform.system',return_value='Windows'),patch('windows_support.shutil.which',return_value=None),patch.dict(os.environ,{'PROGRAMFILES':tmp,'LOCALAPPDATA':tmp}):
            root=Path(tmp)
            for rel in ['Docker/Docker/resources/bin/docker.exe','nodejs/node.exe','Microsoft/WinGet/Links/ffprobe.exe']:
                file=root/rel;file.parent.mkdir(parents=True,exist_ok=True);file.touch()
            self.assertEqual(ws.tool_binary('docker'),str(root/'Docker/Docker/resources/bin/docker.exe'));self.assertEqual(ws.tool_binary('node'),str(root/'nodejs/node.exe'));self.assertEqual(ws.tool_binary('ffprobe'),str(root/'Microsoft/WinGet/Links/ffprobe.exe'))
    def test_readiness_distinguishes_missing_stopped_windows_mode_and_missing_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio=cm.Studio(Path(tmp))
            with patch.object(studio.subscription,'status',return_value={}),patch('windows_support.tool_binary',return_value=None):self.assertIn('not found',studio.health()['message'])
            cases=[([subprocess.CompletedProcess([],1,'','')],'not running'),([subprocess.CompletedProcess([],0,'windows\n','')],'Switch'),([subprocess.CompletedProcess([],0,'linux\n',''),subprocess.CompletedProcess([],1,b'',b'')],'image is missing'),([subprocess.CompletedProcess([],0,'linux\n',''),subprocess.CompletedProcess([],0,b'',b'')],'Ready')]
            for responses,text in cases:
                with self.subTest(text=text),patch.object(studio.subscription,'status',return_value={}),patch('windows_support.tool_binary',side_effect=lambda name:'/installed/'+name),patch('code_motion.subprocess.run',side_effect=responses):
                    value=studio.health();self.assertIn(text,value['message']);self.assertEqual(value['ready'],text=='Ready')
    def test_code_setup_is_distinct_from_legacy_setup(self):
        with patch('windows_support.platform.system',return_value='Windows'):
            self.assertIn('setup_code_motion.ps1',ws.code_setup_command(Path('/repo'))[-1]);self.assertIn('setup_windows.ps1',ws.setup_command(Path('/repo'))[-1])

if __name__=='__main__':unittest.main()
