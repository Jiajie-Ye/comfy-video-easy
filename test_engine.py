import copy,json,tempfile,unittest
from pathlib import Path
import engine as E

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.c=E.defaults();self.c['prompt']='A blue ball on a table.'
        self.profile=E.model_profile()
        self.schema=json.loads((Path(__file__).parent/'tests/fixtures/node_schema.json').read_text('utf-8'))
    def test_first_frame_guides_both_passes_without_changing_reference_order(self):
        self.c.update(images=['a.png','b.png','c.png'],first_frame='c.png',second=True)
        self.schema['LoadImage']['input']['required']['image'][0].extend(['up_a.png','up_b.png','up_c.png'])
        E.validate_settings(self.c);p=E.build_prompt(self.c,{'images':['up_a.png','up_b.png','up_c.png']},'test',self.profile)
        self.assertEqual(p['108']['inputs']['ref_images.ref_image_2'],['1005',0])
        self.assertEqual(p['109']['inputs']['image'],['1004',0]);self.assertEqual(p['109']['inputs']['frame_idx'],0)
        self.assertEqual(p['246']['inputs']['conditioning'],['109',0]);self.assertEqual(p['247']['inputs']['latent_image'],['108',1])
        self.assertEqual(p['299']['inputs']['positive'],['108',0]);self.assertEqual(p['299']['inputs']['latent'],['293',0]);self.assertEqual(p['294']['inputs']['conditioning'],['299',0])
        E.validate_graph(p,self.schema)
        self.c['images']=['c.png','a.png','b.png'];p=E.build_prompt(self.c,{'images':['up_c.png','up_a.png','up_b.png']},'test',self.profile)
        self.assertEqual(p['109']['inputs']['image'],['1000',0])
    def test_missing_first_frame_fails_without_silent_fallback(self):
        self.c['first_frame']='missing.png'
        with self.assertRaises(ValueError):E.validate_settings(self.c)
        self.c['images']=['missing.png']
        with self.assertRaises(ValueError):E.build_prompt(self.c,{},'test',self.profile)
    def test_frames_follow_source_alignment(self):
        self.assertEqual(E.frame_count(10),243)
        for seconds in (5,8,10,12,15):
            self.assertEqual(E.frame_count(seconds)%17,5)
            self.assertLess(E.frame_count(seconds)-seconds*24,17)
    def test_no_reference_leakage_from_source(self):
        p=E.build_prompt(self.c,{},'test',self.profile)
        self.assertFalse(any(k.startswith('ref_images.') for k in p['108']['inputs']))
        self.assertFalse(any(n['class_type'] in ('LoadImage','LoadAudio','VHS_LoadVideo') for n in p.values()))
        self.assertTrue(p['356']['inputs']['save_output'])
        self.assertNotIn('360',p)
        E.validate_graph(p,self.schema)
    def test_fixed_seed_survives_enabling_second_pass(self):
        self.c.update(fixed=True,seed=34567,second_fixed=True,second_seed=8910)
        first=E.concrete_settings(self.c);self.c['second']=True;second=E.concrete_settings(self.c)
        self.assertEqual(first['seed'],second['seed'])
        p=E.build_prompt(second,{},'test',self.profile)
        self.assertEqual(p['243']['inputs']['noise_seed'],34567)
        self.assertEqual(p['300']['inputs']['noise_seed'],8910)
        # Refinement uses base model rather than Turbo LoRA and re-encodes both media.
        self.assertEqual(p['294']['inputs']['model'],['9',0])
        self.assertEqual(p['295']['inputs']['latent_image'],['293',0])
        self.assertEqual(p['293']['inputs']['audio_latent'],['288',0])
        E.validate_graph(p,self.schema)
    def test_ref_numbering_and_optional_video_audio(self):
        p=E.build_prompt(self.c,{'images':['a.png','b.png'],'audios':['a.wav'],'videos':['v.mp4']},'test',self.profile)
        r=p['108']['inputs'];self.assertEqual(r['ref_images.ref_image_1'],['1003',0])
        self.assertEqual(r['ref_audios.ref_audio_0'],['1100',0]);self.assertNotIn('ref_video_audios.ref_video_audio_0',r)
        self.c['video_audio']=True
        p=E.build_prompt(self.c,{'videos':['v.mp4']},'test',self.profile)
        self.assertEqual(p['108']['inputs']['ref_video_audios.ref_video_audio_0'],['1200',2])
        self.assertEqual(p['1200']['inputs']['force_rate'],24)
    def test_invalid_input_is_rejected_before_submission(self):
        for key,value in [('seconds',60),('megapixels',float('nan')),('seed',-1),('second_steps',0),('server','not a url')]:
            c=copy.deepcopy(self.c);c[key]=value
            with self.assertRaises(ValueError):E.validate_settings(c)
    def test_missing_model_or_broken_link_is_visible(self):
        p=E.build_prompt(self.c,{},'test',self.profile);p['9']['inputs']['unet_name']='absent.safetensors'
        with self.assertRaisesRegex(ValueError,'选项'):E.validate_graph(p,self.schema)
        p=E.build_prompt(self.c,{},'test',self.profile);p['247']['inputs']['noise']=['999999',0]
        with self.assertRaisesRegex(ValueError,'不存在'):E.validate_graph(p,self.schema)
    def test_only_own_expected_outputs_are_downloaded(self):
        item={'filename':'a.mp4','type':'output','subfolder':'test'}
        h={'outputs':{'356':{'gifs':[item,item]},'999':{'gifs':[{'filename':'other.mp4'}]},'360':{'gifs':[{'filename':'preview.png'}]}}}
        self.assertEqual(E.result_media(h),[('一采',item)])
    def test_manifest_records_exact_seed_before_submission(self):
        with tempfile.TemporaryDirectory() as d:
            self.c['fixed']=False;c=E.concrete_settings(self.c);j=E.job_create(d,c)
            saved=json.loads((Path(j['folder'])/'task.json').read_text('utf-8'))
            self.assertEqual(saved['settings']['seed'],c['seed']);self.assertNotEqual(c['seed'],self.c['seed'])
    def test_output_name_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.png';p.write_bytes(b'old');q=E.unique_path(p)
            self.assertEqual(q.name,'a_2.png');q.write_bytes(b'new');self.assertEqual(E.unique_path(p).name,'a_3.png')

if __name__=='__main__':unittest.main(verbosity=2)
