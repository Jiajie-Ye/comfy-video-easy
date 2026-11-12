import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import workspaces as W
import engine as E

class WorkspaceTests(unittest.TestCase):
    def test_fixed_locator_ignores_new_executable_folders(self):
        with tempfile.TemporaryDirectory() as d,patch('workspaces.locator',return_value=Path(d).resolve()/'locator.json'):
            W.remember(Path(d).resolve()/'workspace');self.assertEqual(W.startup_workspace(Path(d).resolve()/'new-exe'),Path(d).resolve()/'workspace')
    def test_import_old_folder_and_remap_copied_media(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();out=root/'我的视频数据'/'视频作品';job=out/'job';job.mkdir(parents=True);(job/'task.json').write_text('{}');(job/'video.mp4').write_bytes(b'video');E.atomic_json(root/'我的视频数据'/'settings.json',{'output':str(out)})
            self.assertIn(str(out),W.import_roots(root));self.assertEqual(len(W.manifests([out,out])),1)
            record=W.resolve_job_files({'files':['missing/video.mp4']},job);self.assertEqual(record['files'],[str(job/'video.mp4')])
    def test_switch_copies_settings_and_keeps_old_history(self):
        with tempfile.TemporaryDirectory() as d,patch('workspaces.locator',return_value=Path(d).resolve()/'locator.json'):
            old,new=Path(d).resolve()/'old',Path(d).resolve()/'new';old.mkdir();E.atomic_json(old/'settings.json',{'config':{'prompt':'Keep'},'output':str(old/'视频作品')});(old/'editing_project.json').write_text('{"clips": []}')
            W.switch_workspace(old,new);saved=json.loads((new/'settings.json').read_text('utf-8'));self.assertEqual(saved['config']['prompt'],'Keep');self.assertIn(str(old/'视频作品'),saved['history_roots']);self.assertEqual(saved['output'],str(new/'视频作品'));self.assertTrue((old/'settings.json').exists());self.assertTrue((new/'editing_project.json').exists())
    def test_image_settings_and_results_follow_workspace(self):
        with tempfile.TemporaryDirectory() as d,patch('workspaces.locator',return_value=Path(d).resolve()/'locator.json'):
            old,new=Path(d).resolve()/'old',Path(d).resolve()/'new';E.atomic_json(old/'settings.json',{'config':{},'output':str(old/'videos')});E.atomic_json(old/'image_settings.json',{'protected_key':'encrypted-placeholder'});E.atomic_json(old/'image_draft.json',{'prompt':'Keep scene'});(old/'generated_images').mkdir();(old/'generated_images'/'image.png').write_bytes(b'example')
            W.switch_workspace(old,new);self.assertTrue((new/'image_settings.json').is_file());self.assertTrue((new/'image_draft.json').is_file());self.assertEqual((new/'generated_images'/'image.png').read_bytes(),b'example');self.assertTrue((old/'generated_images'/'image.png').exists())
    def test_existing_destination_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d,patch('workspaces.locator',return_value=Path(d).resolve()/'locator.json'):
            old,new=Path(d).resolve()/'old',Path(d).resolve()/'new';E.atomic_json(old/'settings.json',{'config':{'prompt':'old'},'output':str(old/'videos')});E.atomic_json(new/'settings.json',{'config':{'prompt':'new'},'output':str(new/'videos')});W.switch_workspace(old,new);saved=json.loads((new/'settings.json').read_text('utf-8'));self.assertEqual(saved['config']['prompt'],'new');self.assertIn(str(old/'videos'),saved['history_roots'])
if __name__=='__main__':unittest.main()
