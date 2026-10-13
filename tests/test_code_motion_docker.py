"""Opt-in production sandbox integration: no API key or live provider required."""
import json
import os
from pathlib import Path
import shutil
import time
import unittest
from unittest.mock import patch
import code_motion as cm

@unittest.skipUnless(os.environ.get('CODE_MOTION_DOCKER_TESTS')=='1','Docker render integration is opt-in')
class DockerRenderTest(unittest.TestCase):
    def wait(self,studio,id):
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            job=studio.get(id)
            if job['status'] in {'complete','error','cancelled'}:
                self.assertEqual(job['status'],'complete',job.get('details',job['message']));return job
            time.sleep(.2)
        studio.cancel(id);self.fail('Sandbox integration test timed out')
    def test_A_B_C_D_generation_preview_revision_and_exports(self):
        root=Path('test-render-output').resolve();root.mkdir(exist_ok=True);studio=cm.Studio(root)
        cases=[('financial',8,'720p',False,'mp4'),('kinetic',6,'1080p',False,'hq'),('overlay',3,'720p',True,'prores'),('audio',5,'720p',False,'mp4')]
        results=[]
        for name,seconds,resolution,transparent,fmt in cases:
            with self.subTest(name=name):
                body={'provider':'ollama','model':'fixture-model','prompt':f'Test {name}','duration':seconds,'resolution':resolution,'transparent':transparent,'auto_review':False}
                if name=='audio':
                    import subprocess
                    audio=root/'timing.wav';subprocess.run(['ffmpeg','-y','-f','lavfi','-i','sine=frequency=110:duration=5',str(audio)],check=True,capture_output=True)
                    body['audio']=studio.upload('timing.wav',audio.read_bytes())['id'];body['beats']=[{'time':.5,'label':'TITLE'},{'time':2,'label':'IMPACT'},{'time':4,'label':'REVEAL'}]
                source=(cm.ENGINE/'examples'/f'{name}.tsx').read_text()
                with patch.object(cm.Provider,'generate',return_value={'source':source,'design_notes':'Trusted fixture, provider mocked','review_frames':[12,24]}):
                    id=studio.start(body);job=self.wait(studio,id)
                    exported=studio.start({'format':fmt,'approved':True},id,'export');result=self.wait(studio,exported)
                    if name=='financial':
                        revised=studio.start({'prompt':'Keep the graph and labels'},id,'revise');self.wait(studio,revised)
                    if name=='overlay':
                        png=studio.start({'format':'png','approved':True},id,'export');self.wait(studio,png)
                        editable=studio.start({'format':'project','approved':True},id,'export');self.wait(studio,editable)
                results.append({'case':name,'preview_job':id,'export_job':exported,'metadata':result['metadata']})
        (root/'results.json').write_text(json.dumps(results,indent=2))
