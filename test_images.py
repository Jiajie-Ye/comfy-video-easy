import base64,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtCore import QByteArray,QBuffer,QIODevice
from PyQt6.QtGui import QImage,QColor
from PyQt6.QtWidgets import QApplication,QDialog
import image_service as I
from image_ui import ImageCreator,ImageSettings
from modern_app import Window
APP=QApplication.instance() or QApplication([])

def png():
    image=QImage(16,12,QImage.Format.Format_RGB32);image.fill(QColor('blue'));data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG');return bytes(data)
def cfg(kind='images'):return dict(kind=kind,url='https://provider.example/v1',model='image-model',api_key='unit-test-secret')
def response(data,status=200):
    r=Mock(status_code=status);r.iter_content.return_value=[json.dumps(data).encode()];return r

class ImageServiceTests(unittest.TestCase):
    def test_endpoint_switch_and_native_gemini(self):
        c=cfg();c['url']='https://provider.example/v1/images/generations';self.assertEqual(I.endpoint(c,True),'https://provider.example/v1/images/edits');self.assertEqual(I.endpoint(c,False),c['url'])
        c.update(kind='gemini',url='https://provider.example',model='models/gemini-image');self.assertEqual(I.endpoint(c,True),'https://provider.example/v1beta/models/gemini-image:generateContent')
    def test_reference_uploads_and_response_persist(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'private-name.png';p.write_bytes(png());session=Mock();session.post.return_value=response({'data':[{'b64_json':base64.b64encode(png()).decode()}]})
            paths=I.generate(cfg(),'A character',[str(p)],d,session);self.assertTrue(Path(paths[0]).is_file());args=session.post.call_args.kwargs
            self.assertIn('data',args);self.assertNotIn('json',args);self.assertEqual(args['files'][0][0],'image[]');self.assertEqual(args['files'][0][1][0],'reference_1.png');self.assertFalse(args['allow_redirects']);session.post.assert_called_once()
            metadata=Path(paths[0]).with_suffix('.json').read_text('utf-8');self.assertNotIn('unit-test-secret',metadata);self.assertNotIn('private-name',metadata)
    def test_text_only_and_gemini_payload(self):
        _,headers,body,files=I.request_data(cfg(),'Scene',[]);self.assertIsNone(files);self.assertEqual(body['n'],1)
        _,headers,body,files=I.request_data(cfg('gemini'),'Character',[png()]);self.assertEqual(headers['x-goog-api-key'],'unit-test-secret');self.assertIn('IMAGE',body['generationConfig']['responseModalities']);self.assertEqual(len(body['contents'][0]['parts']),2)
        data={'candidates':[{'content':{'parts':[{'thought':True,'inlineData':{'data':'not-image'}},{'inlineData':{'data':base64.b64encode(png()).decode(),'mimeType':'image/png'}}]}}]};self.assertEqual(I.parse_images('gemini',data),[png()])
    def test_errors_no_secrets_no_retry_and_invalid_images(self):
        session=Mock();session.post.return_value=response({},401)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(I.ImageError) as error:I.generate(cfg(),'Scene',[],d,session)
            self.assertNotIn('unit-test-secret',str(error.exception));session.post.assert_called_once()
            with self.assertRaises(I.ImageError):I.save_images(d,[b'not an image'])
        with self.assertRaises(I.ImageError):I.parse_images('images',{'data':[]})
        with self.assertRaises(I.ImageError):I.request_data(cfg(),' ',[])
    def test_provider_error_details_are_redacted_and_not_retried(self):
        session=Mock();session.post.return_value=response({'error':{'code':'unsupported_endpoint','message':'Use image API. unit-test-secret Bearer other-token https://provider.example/v1 exact private prompt','request_id':'req-test'}},400)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(I.ImageError) as error:I.generate(cfg(),'exact private prompt',[],d,session)
        text=str(error.exception);self.assertIn('unsupported_endpoint',text);self.assertIn('req-test',text)
        for private in ['unit-test-secret','other-token','https://provider.example/v1','exact private prompt']:self.assertNotIn(private,text)
        session.post.assert_called_once();session.post.return_value.close.assert_called_once()
    def test_error_categories_and_unreadable_body(self):
        for code,expected in [('content_policy_violation','内容审核'),('insufficient_user_quota','额度'),('model_not_found','分组')]:
            r=response({'error':{'code':code,'message':'group cannot route model' if code=='model_not_found' else 'rejected'}},400)
            self.assertIn(expected,str(I.api_error(r,cfg(),'draft')))
        r=Mock(status_code=503);r.iter_content.return_value=[b'<html>unit-test-secret</html>']
        error=str(I.api_error(r,cfg(),'draft'));self.assertIn('HTTP 503',error);self.assertNotIn('<html>',error);self.assertNotIn('unit-test-secret',error)
    def test_image_download_has_no_provider_credentials(self):
        client=Mock();r=Mock(status_code=200);r.iter_content.return_value=[png()];client.get.return_value=r
        with patch('image_service.requests.Session') as session:
            session.return_value.__enter__.return_value=client
            self.assertEqual(I.download('https://cdn.example/image.png'),png());self.assertNotIn('headers',client.get.call_args.kwargs);self.assertFalse(client.get.call_args.kwargs['allow_redirects'])
    @unittest.skipUnless(os.name=='nt','Windows encryption')
    def test_independent_encrypted_settings(self):
        with tempfile.TemporaryDirectory() as d:
            I.save_config(d,cfg());self.assertEqual(I.load_config(d)['api_key'],'unit-test-secret');self.assertNotIn('unit-test-secret',(Path(d)/'image_settings.json').read_text('utf-8'));self.assertFalse((Path(d)/'enhancer_settings.json').exists())

class ImageUITests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=Window(self.tmp.name)
    def tearDown(self):self.w.close();self.w.deleteLater();APP.processEvents();self.tmp.cleanup()
    def test_first_use_cancel_keeps_prompt_and_no_request(self):
        dialog=ImageCreator(self.w);dialog.prompt.setPlainText('My scene')
        with patch.object(dialog,'configure',return_value=None),patch('image_ui.I.generate') as generate:dialog.generate();generate.assert_not_called()
        self.assertEqual(dialog.prompt.toPlainText(),'My scene');dialog.reject()
    def test_preview_insert_capacity_and_reload_history(self):
        paths=I.save_images(self.tmp.name,[png()]);dialog=ImageCreator(self.w);self.assertEqual(dialog.results.count(),1);self.assertFalse(dialog.preview.original.isNull())
        self.w.pickers['images'].paths=['x'+str(i) for i in range(9)];dialog.use_result();self.assertIsNone(dialog.result_path)
        self.w.pickers['images'].paths=[];dialog.use_result();self.assertEqual(dialog.result_path,paths[0]);self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
    def test_confirmed_image_is_inserted_without_changing_video_prompt(self):
        paths=I.save_images(self.tmp.name,[png()]);self.w.prompt.setPlainText('Keep video story')
        with patch('modern_app.ImageCreator') as creator:
            creator.return_value.exec.return_value=QDialog.DialogCode.Accepted;creator.return_value.result_path=paths[0];self.w.create_reference_image()
        self.assertEqual(self.w.pickers['images'].paths,paths);self.assertEqual(self.w.prompt.toPlainText(),'Keep video story')
    def test_background_generation_finishes_and_enables_insert(self):
        import time
        paths=I.save_images(self.tmp.name,[png()]);dialog=ImageCreator(self.w);dialog.prompt.setPlainText('A landscape')
        with patch('image_ui.I.load_config',return_value=cfg()),patch('image_ui.I.generate',return_value=paths) as generate:
            dialog.generate();deadline=time.monotonic()+3
            while dialog.busy and time.monotonic()<deadline:APP.processEvents();time.sleep(.01)
            self.assertFalse(dialog.busy);generate.assert_called_once();self.assertTrue(dialog.insert.isEnabled());self.assertFalse(dialog.preview.original.isNull())
        dialog.reject()
    def test_failed_generation_restores_controls_and_keeps_previous_result(self):
        I.save_images(self.tmp.name,[png()]);dialog=ImageCreator(self.w);dialog.busy=True;dialog.inputs.setEnabled(False);dialog.finished([],'test failure');self.assertTrue(dialog.inputs.isEnabled());self.assertTrue(dialog.insert.isEnabled());self.assertEqual(dialog.results.count(),1);self.assertIn('历史',dialog.result_heading.text());self.assertTrue(dialog.error_details_button.isHidden() is False);self.assertEqual(json.loads((self.w.data/'image_error.json').read_text('utf-8'))['error'],'test failure');dialog.reject()

if __name__=='__main__':unittest.main()
