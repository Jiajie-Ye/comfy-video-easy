import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import prompt_enhancer as P

class EnhancerTests(unittest.TestCase):
    def config(self,kind='chat'):
        c=P.defaults();c.update(kind=kind,url='https://provider.example/v1',api_key='test-private-key',model='sample-model');return c
    def test_endpoints(self):
        c=self.config();self.assertEqual(P.endpoint(c),'https://provider.example/v1/chat/completions')
        c['url']='https://provider.example/v1/chat/completions';self.assertEqual(P.endpoint(c),c['url'])
        c.update(url='https://provider.example',kind='responses');self.assertTrue(P.endpoint(c).endswith('/v1/responses'))
        c.update(kind='gemini',url='https://provider.example/v1beta',model='models/example');self.assertTrue(P.endpoint(c).endswith('/v1beta/models/example:generateContent'))
        c.update(kind='bedrock',url='https://provider.example',model='region.model:0');self.assertTrue(P.endpoint(c).endswith('/model/region.model%3A0/converse'))
    def test_five_provider_payloads_and_parsers(self):
        payloads={
            'chat':{'choices':[{'message':{'content':'enhanced'}}]},
            'responses':{'output':[{'type':'message','content':[{'type':'output_text','text':'enhanced'}]}]},
            'anthropic':{'content':[{'type':'text','text':'enhanced'}]},
            'gemini':{'candidates':[{'content':{'parts':[{'text':'secret reasoning','thought':True},{'text':'enhanced'}]}}]},
            'bedrock':{'output':{'message':{'content':[{'text':'enhanced'}]}}}}
        for kind,_ in P.KINDS:
            c=self.config(kind);url,headers,body=P.request_data(c,'中文剧情',dict(seconds=10,images=2,server='private-server',files=['private-image.png']))
            serialized=json.dumps(body);self.assertNotIn('private-server',serialized);self.assertNotIn('private-image',serialized);self.assertNotIn(c['api_key'],url);self.assertNotIn(c['api_key'],serialized)
            response=Mock(status_code=200);response.json.return_value=payloads[kind];session=Mock();session.post.return_value=response
            self.assertEqual(P.enhance(c,'story',{'seconds':10},session),'enhanced');self.assertFalse(session.post.call_args.kwargs['allow_redirects']);session.post.assert_called_once()
    def test_selected_duration_is_authoritative_for_every_provider(self):
        for kind,_ in P.KINDS:
            for seconds in (1,5,15):
                c=self.config(kind);c['template']='Example: 10 seconds, shots 0-5 and 5-10'
                _,_,body=P.request_data(c,'A 20-second walk with Chinese dialogue',dict(seconds=seconds))
                system={'chat':lambda:body['messages'][0]['content'],'responses':lambda:body['instructions'],'anthropic':lambda:body['system'],'gemini':lambda:body['systemInstruction']['parts'][0]['text'],'bedrock':lambda:body['system'][0]['text']}[kind]()
                self.assertIn(f'current UI target is exactly {seconds} seconds',system)
                self.assertIn(f'ending at exactly {seconds} seconds',system)
                self.assertIn('overrides any duration or timestamps',system)
    def test_missing_or_invalid_duration_is_rejected(self):
        for seconds in (None,0,16,True,5.5,'10'):
            with self.assertRaises(P.EnhancementError):P.request_data(self.config(),'story',dict(seconds=seconds))
    def test_first_frame_choice_is_in_enhancement_instructions(self):
        _,_,body=P.request_data(self.config(),'Begin with Picture 1',dict(seconds=5,images=3,first_frame_picture=3))
        self.assertIn('<Picture 3> as the first-frame guide',body['messages'][0]['content'])
        with self.assertRaises(P.EnhancementError):P.request_data(self.config(),'story',dict(seconds=5,images=2,first_frame_picture=3))
    def test_secret_safe_errors_and_redirects(self):
        c=self.config();response=Mock(status_code=401,text='test-private-key');session=Mock();session.post.return_value=response
        with self.assertRaises(P.EnhancementError) as error:P.enhance(c,'story',{'seconds':10},session)
        self.assertNotIn(c['api_key'],str(error.exception));response.status_code=302
        with self.assertRaises(P.EnhancementError):P.enhance(c,'story',{'seconds':10},session)
    def test_truncated_outputs_rejected(self):
        for kind,data in [('chat',{'choices':[{'finish_reason':'length'}]}),('responses',{'status':'incomplete'}),('anthropic',{'stop_reason':'max_tokens'}),('gemini',{'candidates':[{'finishReason':'MAX_TOKENS'}]}),('bedrock',{'stopReason':'max_tokens'})]:
            with self.assertRaises(P.EnhancementError):P.parse_response(kind,data)
    def test_invalid_urls_and_empty_story(self):
        for url in ['file:///tmp/key','https://user:secret@example.com','https://example.com?key=secret']:
            c=self.config();c['url']=url
            with self.assertRaises(P.EnhancementError):P.validate(c)
        with self.assertRaises(P.EnhancementError):P.request_data(self.config(),' ',{})
    def test_reference_analysis_all_protocols(self):
        for kind,_ in P.KINDS:
            _,_,body=P.request_data(self.config(kind),'角色1跟角色2，图片3是首帧',dict(seconds=5,images=4),analysis=True)
            text=json.dumps(body,ensure_ascii=False)
            self.assertIn('角色2 means Picture 2',text);self.assertIn('Unmentioned images',text)
            self.assertNotIn('reference_format',text)
    def test_reference_mapping_parse_and_validation(self):
        value=dict(bindings=[dict(entity='角色1',picture=1),dict(entity='角色2',picture=2)],first_frame_picture=3)
        with patch.object(P,'enhance',return_value='```json\n'+json.dumps(value)+'\n```'):
            self.assertEqual(P.analyze_references(self.config(),'story',dict(seconds=5,images=4)),value)
        for bad in [dict(bindings=[dict(entity='x',picture=5)]),dict(bindings=[],first_frame_picture=True),dict(bindings='oops')]:
            with self.assertRaises(P.EnhancementError):P.validate_plan(bad,4)
    def test_confirmed_mapping_and_output_guard(self):
        plan=dict(bindings=[dict(entity='角色1',picture=2)],first_frame_picture=3)
        _,_,body=P.request_data(self.config(),'角色1',dict(seconds=5,images=4,reference_plan=plan,first_frame_picture=3))
        self.assertIn('AUTHORITATIVE REFERENCE PLAN',body['messages'][0]['content'])
        self.assertEqual(json.loads(body['messages'][1]['content'])['video_context']['reference_plan'],plan)
        P.check_reference_output('<Picture 2> moves, opening <Picture 3>',plan)
        for text in ['<Picture 1> <Picture 2> <Picture 3>','<Picture 2>']:
            with self.assertRaises(P.EnhancementError):P.check_reference_output(text,plan)
    def test_reference_review_edit_and_unused(self):
        from PyQt6.QtWidgets import QApplication,QWidget,QLabel,QPushButton
        from enhancer_ui import ReferenceReview
        app=QApplication.instance() or QApplication([])
        class Host(QWidget):
            t=staticmethod(lambda zh,en:zh)
            def label(self,text,*args):return QLabel(text)
            def button(self,text,slot,*args):
                b=QPushButton(text);b.clicked.connect(slot);return b
            def info(self,text):raise AssertionError(text)
        host=Host();host.resize(1200,850)
        plan=dict(bindings=[dict(entity='角色1',picture=1),dict(entity='角色2',picture=2)],first_frame_picture=3)
        d=ReferenceReview(host,'角色1和角色2，图片3是首帧',['none']*4,plan)
        self.assertIn('<Picture 4>',d.unused.text());self.assertNotIn('<Picture 3>',d.unused.text())
        d.rows[0][2].setCurrentIndex(4);d.first.setCurrentIndex(1);d.apply()
        self.assertEqual(d.result_plan['bindings'][0]['picture'],4);self.assertEqual(d.result_plan['first_frame_picture'],1)
        d.deleteLater();host.deleteLater()
    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_key_is_encrypted_on_disk_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as folder:
            c=self.config();P.save_config(folder,c);stored=(Path(folder)/'enhancer_settings.json').read_text('utf-8');self.assertNotIn(c['api_key'],stored);self.assertEqual(P.load_config(folder)['api_key'],c['api_key']);self.assertEqual(P.load_config(folder)['template'],c['template'])

if __name__=='__main__':unittest.main()
