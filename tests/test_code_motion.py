"""Code Motion orchestration/security tests. Real Remotion media: npm run smoke."""
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch, MagicMock
from http.server import ThreadingHTTPServer
from PIL import Image
import app
import code_motion as cm

SOURCE=(cm.ENGINE/'examples/overlay.tsx').read_text()
BODY={'prompt':'Show a $500 credit card overlay','model':'test-model','duration':3,'transparent':True,'auto_review':False}

class CodeMotionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.studio=cm.Studio(Path(self.tmp.name));self.addCleanup(self.tmp.cleanup)
    def start(self,body=None,parent=None,action='generate'):
        with patch.object(self.studio,'health',return_value={'ready':True}),patch.dict(os.environ,{'OPENAI_API_KEY':'not-a-real-key'}),patch('code_motion.threading.Thread'):
            return self.studio.start(body or BODY,parent,action)
    def fake_worker(self,id,mode):
        p=self.studio.projects/id
        (p/'preview.mp4').write_bytes(b'trusted-mocked-video');(p/'index.tsx').write_text('trusted entry');(p/'fonts.css').write_text('');(p/'frames').mkdir(exist_ok=True)
        Image.new('RGB',(64,36),'navy').save(p/'frames/0.png')
    def preview(self,body=None):
        id=self.start(body);config=json.loads((self.studio.projects/id/'job.json').read_text())
        with patch.object(cm.Provider,'generate',return_value={'source':SOURCE,'design_notes':'Clear overlay','review_frames':[10]}),patch.object(self.studio,'run_worker',side_effect=self.fake_worker),patch.object(self.studio,'verify_video',return_value={}):
            self.studio.pipeline(id,config,'generate','mp4')
        self.assertEqual(self.studio.get(id)['status'],'complete');return id
    def test_ai_metadata_changes_preview_settings_and_persists_exact_export_config(self):
        id=self.start({**BODY,'auto_metadata':True});cfg=json.loads((self.studio.projects/id/'job.json').read_text())
        plan={'duration':5,'resolution':'vertical','aspect':'9:16','fps':24,'structure':'Three sequential reveals'}
        scene={'source':SOURCE,'design_notes':'overlay','review_frames':[10]}
        with patch.object(cm.Provider,'generate',side_effect=[plan,scene]) as provider,patch.object(self.studio,'run_worker',side_effect=self.fake_worker),patch.object(self.studio,'verify_video',return_value={}):self.studio.pipeline(id,cfg,'generate','mp4')
        job=self.studio.get(id);self.assertEqual(job['status'],'complete');self.assertEqual(job['config']['durationInFrames'],120);self.assertEqual(job['config']['height'],1920);self.assertEqual(provider.call_count,2)
        request=json.loads((self.studio.projects/id/'request.json').read_text());self.assertFalse(request['auto_metadata']);self.assertEqual(request['duration'],5)
    def test_real_renderer_fixture_metadata_and_alpha_verification(self):
        if not (cm.ENGINE/'smoke-output/overlay/animation.mov').exists():self.skipTest('Run npm run smoke first')
        config={'width':1280,'height':720,'fps':24,'durationInFrames':72,'transparent':True}
        info=self.studio.verify_video(cm.ENGINE/'smoke-output/overlay/animation.mov',config);self.assertEqual(info['codec'],'prores');self.assertIn('a',info['pixel_format'])

    def test_settings_dimensions_duration_and_beats(self):
        c=cm.settings({**BODY,'resolution':'vertical','beats':[{'time':.5,'label':'enter'}]})
        self.assertEqual((c['width'],c['height'],c['fps'],c['durationInFrames']),(1080,1920,24,72));self.assertEqual(c['beats'][0]['frame'],12)
    def test_invalid_settings_fail(self):
        for change in [{'duration':float('nan')},{'duration':0},{'fps':24.5},{'transparent':'true'},{'max_revisions':10},{'beats':[{'time':4}]},{'assets':['../keys']},{'provider':'unknown'}]:
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):cm.settings({**BODY,**change})
    def test_upload_and_svg_active_content(self):
        image=io.BytesIO();Image.new('RGB',(32,32)).save(image,'PNG');asset=self.studio.upload('../../logo.png',image.getvalue());self.assertEqual(asset['name'],'logo.png');self.assertEqual(self.studio.asset(asset['id']),asset)
        for data in [b'<svg><script/></svg>',b'<svg><image href="file:///secret"/></svg>',b'<!DOCTYPE svg><svg/>',b'<svg><path onload="evil"/></svg>']:
            with self.assertRaises(ValueError):self.studio.upload('evil.svg',data)
        good=self.studio.upload('icon.svg',b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L1 1"/></svg>');self.assertEqual(good['kind'],'svg')
    def test_asset_path_and_file_traversal(self):
        for id in ['../secret','a'*13,'bad']:
            with self.assertRaises(ValueError):self.studio.asset(id)
        with self.assertRaises(ValueError):self.studio.file('a'*12,'../keys')
    def test_secure_worker_command_and_timeout_cleanup(self):
        id=self.start();process=MagicMock();process.stdout=iter(['{"stage":"complete","progress":1}\n']);process.wait.return_value=0;process.poll.return_value=0
        with patch('code_motion.os.chown'),patch('code_motion.subprocess.Popen',return_value=process) as spawn,patch('code_motion.subprocess.run') as cleanup:
            self.studio.run_worker(id,'preview')
        cmd=spawn.call_args.args[0]
        self.assertIn('--network',cmd);self.assertEqual(cmd[cmd.index('--network')+1],'none');self.assertIn('--read-only',cmd);self.assertIn('no-new-privileges',cmd);self.assertIn('--cap-drop',cmd);self.assertIn('--memory',cmd)
        self.assertEqual(cmd.count('--mount'),1);self.assertNotIn('--env',cmd);self.assertNotIn('OPENAI_API_KEY',' '.join(cmd));self.assertEqual(cleanup.call_args.args[0],[cmd[0],'rm','-f','motion-studio-'+id])
    def test_no_unsafe_host_fallback(self):
        with patch.object(self.studio,'health',return_value={'ready':False}),self.assertRaisesRegex(ValueError,'Docker'):
            self.studio.start({**BODY,'provider':'ollama'})
    def test_preview_persists_and_requires_approval(self):
        id=self.preview();recovered=cm.Studio(Path(self.tmp.name));self.assertEqual(recovered.get(id)['status'],'complete')
        with self.assertRaisesRegex(ValueError,'Approve'):self.start({'format':'prores'},id,'export')
        with self.assertRaisesRegex(ValueError,'MP4'):self.start({'format':'mp4','approved':True},id,'export')
    def test_editable_project_export(self):
        import zipfile
        id=self.preview();export=self.start({'format':'project','approved':True},id,'export');config=json.loads((self.studio.projects/export/'job.json').read_text());self.studio.pipeline(export,config,'export','project')
        self.assertEqual(self.studio.get(export)['status'],'complete')
        with zipfile.ZipFile(self.studio.projects/export/'project.zip') as z:
            self.assertIn('Scene.tsx',z.namelist());self.assertNotIn('request.json',z.namelist());self.assertNotIn('state.json',z.namelist());self.assertNotIn('OPENAI_API_KEY',z.read('package.json').decode())
    def test_revision_keeps_source_assets_and_settings(self):
        id=self.preview();new=self.start({'prompt':'Make the amount larger'},id,'revise');cfg=json.loads((self.studio.projects/new/'job.json').read_text());self.assertEqual(cfg['width'],1920);self.assertTrue(cfg['transparent']);self.assertEqual((self.studio.projects/new/'Scene.tsx').read_text(),SOURCE)
    def test_cancellation_prevents_generation(self):
        id=self.start();self.studio.cancel(id);cfg=json.loads((self.studio.projects/id/'job.json').read_text())
        with patch.object(cm.Provider,'generate') as gen:self.studio.pipeline(id,cfg,'generate','mp4');gen.assert_not_called()
        self.assertEqual(self.studio.get(id)['status'],'cancelled')
    def test_review_bound_and_before_after(self):
        id=self.start({**BODY,'auto_review':True,'max_revisions':1});cfg=json.loads((self.studio.projects/id/'job.json').read_text())
        with patch.object(cm.Provider,'generate',return_value={'source':SOURCE,'design_notes':'overlay','review_frames':[10]}),patch.object(self.studio,'run_worker',side_effect=self.fake_worker) as worker,patch.object(self.studio,'verify_video',return_value={}),patch.object(self.studio,'review',return_value={'needs_revision':True,'feedback':['Frame 10: enlarge text']}) as review:
            self.studio.pipeline(id,cfg,'generate','mp4')
        self.assertEqual(review.call_count,2);self.assertEqual(worker.call_count,2);self.assertTrue(self.studio.get(id)['before']);self.assertEqual(self.studio.get(id)['status'],'complete')
    def test_renderer_errors_are_repaired_but_bounded(self):
        id=self.start();cfg=json.loads((self.studio.projects/id/'job.json').read_text())
        with patch.object(cm.Provider,'generate',return_value={'source':SOURCE,'design_notes':'overlay','review_frames':[]}) as gen,patch.object(self.studio,'run_worker',side_effect=ValueError('Type error')):
            self.studio.pipeline(id,cfg,'generate','mp4')
        self.assertEqual(gen.call_count,3);self.assertEqual(self.studio.get(id)['status'],'error')
    def test_failed_visual_revision_restores_preview_and_source(self):
        id=self.start({**BODY,'auto_review':True,'max_revisions':1});cfg=json.loads((self.studio.projects/id/'job.json').read_text())
        def worker(id,mode):
            if (self.studio.projects/id/'before-0.mp4').exists(): raise ValueError('broken revision')
            self.fake_worker(id,mode)
        with patch.object(cm.Provider,'generate',return_value={'source':SOURCE,'design_notes':'overlay','review_frames':[]}),patch.object(self.studio,'run_worker',side_effect=worker),patch.object(self.studio,'verify_video',return_value={}),patch.object(self.studio,'review',return_value={'needs_revision':True,'feedback':['Move title']}):self.studio.pipeline(id,cfg,'generate','mp4')
        self.assertEqual(self.studio.get(id)['status'],'complete');self.assertEqual((self.studio.projects/id/'preview.mp4').read_bytes(),b'trusted-mocked-video');self.assertIn('retained',self.studio.get(id)['history'][-1]['feedback'][0])
    def test_style_saved_and_reloaded(self):
        key=self.studio.save_style('Editorial','Deep blue, large white type');self.assertEqual(cm.Studio(Path(self.tmp.name)).styles()[key]['name'],'Editorial')
    def test_openai_request_images_schema_and_key_stay_backend(self):
        result={'source':SOURCE,'design_notes':'layout','review_frames':[]};response=MagicMock();response.__enter__.return_value=response;response.read.return_value=json.dumps({'output':[{'content':[{'type':'output_text','text':json.dumps(result)}]}]}).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-secret'}),patch('code_motion.urllib.request.urlopen',return_value=response) as call:
            self.assertEqual(cm.Provider('openai','configurable-model').generate('instructions','prompt',cm.SCENE_SCHEMA,['data:image/png;base64,a']),result)
        req=call.call_args.args[0];payload=json.loads(req.data);self.assertEqual(payload['model'],'configurable-model');self.assertFalse(payload['store']);self.assertEqual(payload['input'][0]['content'][1]['type'],'input_image');self.assertNotIn('test-secret',req.data.decode())
    def test_openai_error_redacts_response(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-secret'}),patch('code_motion.urllib.request.urlopen',side_effect=urllib.error.HTTPError('url',401,'secret',{},None)),self.assertRaisesRegex(ValueError,'HTTP 401') as error:cm.Provider('openai','model').generate('i','p',cm.SCENE_SCHEMA)
        self.assertNotIn('secret',str(error.exception))

class CodeMotionHTTPTest(unittest.TestCase):
    def test_authorization_logs_and_range_download(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'CODE_STUDIO',cm.Studio(Path(tmp))):
            studio=app.CODE_STUDIO;id='a'*12;p=studio.projects/id;p.mkdir();(p/'preview.mp4').write_bytes(b'0123456789')
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                req=urllib.request.Request(base+'/api/code-motion/styles',data=b'{"name":"x","direction":"y"}')
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                self.assertEqual(error.exception.code,403)
                req.add_header('X-Code-Motion-Token',app.CODE_MOTION_TOKEN);req.add_header('Origin','https://evil.example')
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(req)
                req.remove_header('Origin')
                with urllib.request.urlopen(req) as r:self.assertEqual(r.status,201)
                req=urllib.request.Request(base+f'/api/code-motion/files/{id}/preview.mp4',headers={'Range':'bytes=2-5'})
                with urllib.request.urlopen(req) as r:self.assertEqual(r.status,206);self.assertEqual(r.read(),b'2345')
            finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
