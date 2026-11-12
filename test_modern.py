import json, tempfile, unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication,QPushButton,QLabel
from modern_app import Window
import engine as E

APP=QApplication.instance() or QApplication([])
class ModernTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=Window(self.tmp.name);self.w.show();APP.processEvents()
    def tearDown(self):
        self.w.busy=False;self.w.close();self.w.deleteLater();APP.processEvents();self.tmp.cleanup()
    def test_duration_range_and_language_preservation(self):
        from PyQt6.QtCore import Qt,QPoint,QPointF
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtTest import QTest
        spin=self.w.controls['seconds']
        self.assertEqual((spin.minimum(),spin.maximum()),(1,15))
        for seconds in range(1,16):
            spin.setValue(seconds);self.w.capture();c=self.w.typed_config();c['prompt']='A blue ball'
            E.validate_settings(c);self.assertEqual(c['seconds'],seconds)
        spin.setValue(3)
        event=QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(0,0),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        APP.sendEvent(spin,event);self.assertEqual(spin.value(),4)
        spin.setFocus();QTest.keyClick(spin,Qt.Key.Key_Down);self.assertEqual(spin.value(),3)
        self.w.toggle_language();self.assertEqual(self.w.controls['seconds'].value(),3)
        self.w.capture();self.assertEqual(self.w.typed_config()['seconds'],3)
    def test_result_buttons_share_task_action_row(self):
        w=self.w;w.stack.setCurrentIndex(1);APP.processEvents()
        folder=next(b for b in w.findChildren(QPushButton) if b.text()=='打开文件夹')
        self.assertEqual(w.play_button.geometry().y(),folder.geometry().y())
        self.assertEqual(w.frame_button.geometry().y(),folder.geometry().y())
        self.assertGreater(w.play_button.geometry().x(),folder.geometry().x())
        self.assertGreater(w.frame_button.geometry().x(),w.play_button.geometry().x())
    def test_toggle_preserves_all_inputs_and_tool_state(self):
        w=self.w;w.prompt.setPlainText('Scene description\n“你好！”');w.pickers['images'].paths=['C:/ref/b.png','C:/ref/a.png'];w.pickers['images'].refresh()
        w.controls['seed'].setText('9007199254740990');w.controls['fixed'].setChecked(True);w.video_edit.setText('C:/videos/a.mp4');w.dir_edit.setText('C:/frames')
        w.capture();before=json.dumps(w.config,sort_keys=True);w.toggle_language();APP.processEvents()
        self.assertEqual(w.lang,'en');self.assertEqual(w.title.text(),'Create video');self.assertEqual(w.prompt.toPlainText(),'Scene description\n“你好！”');w.capture()
        self.assertEqual(before,json.dumps(w.config,sort_keys=True));self.assertEqual(w.video_edit.text(),'C:/videos/a.mp4')
        w.toggle_language();self.assertEqual(w.title.text(),'制作视频');self.assertEqual(w.controls['seed'].text(),'9007199254740990')
    def test_language_is_persisted_and_old_preferences_supported(self):
        self.w.toggle_language();saved=json.loads((Path(self.tmp.name)/'settings.json').read_text('utf-8'));self.assertEqual(saved['language'],'en')
        other=Window(self.tmp.name);self.assertEqual(other.lang,'en');other.close();other.deleteLater()
    def test_switch_while_busy_keeps_task_state_and_disables_submission(self):
        w=self.w;w.busy=True;w.sync_busy();w.on_event('status','服务器正在生成，请耐心等待…');w.toggle_language()
        self.assertTrue(w.busy);self.assertFalse(w.run.isEnabled());self.assertEqual(w.status.text(),'Generating on the server…')
        w.on_event('status','排队中，当前等待位置 2');self.assertEqual(w.status.text(),'Queued · position 2')
        w.on_event('idle',None);self.assertTrue(w.run.isEnabled())
    def test_history_language_and_selection_survive_switch(self):
        w=self.w;c=E.defaults();c['prompt']='A ball';j=E.job_create(w.output,c);j['status']='已完成';E.save_job(j);w.selected_id=j['id'];w.refresh_history()
        self.assertEqual(w.selected_job()['id'],j['id']);w.toggle_language();self.assertEqual(w.table.item(0,1).text(),'Completed');self.assertEqual(w.selected_job()['id'],j['id'])
        w.load_job();self.assertTrue(w.controls['fixed'].isChecked())
    def test_english_navigation_and_buttons_do_not_keep_chinese_labels(self):
        self.w.toggle_language();APP.processEvents()
        import re
        for b in self.w.findChildren(QPushButton):
            if b is self.w.language:continue
            self.assertFalse(re.search('[\u4e00-\u9fff]',b.text()),b.text())
    def test_partial_numeric_edit_does_not_block_language_switch(self):
        self.w.controls['steps'].setText('');self.w.toggle_language();self.assertEqual(self.w.controls['steps'].text(),'')
    def test_minimum_layout_keeps_primary_action_and_prompt_visible(self):
        w=self.w;w.resize(1000,720);APP.processEvents()
        self.assertGreater(w.prompt.width(),250);self.assertGreater(w.run.width(),100)
        self.assertLessEqual(w.run.mapTo(w,w.run.rect().bottomRight()).x(),w.width())
        self.assertLessEqual(w.run.mapTo(w,w.run.rect().bottomRight()).y(),w.height())
    def test_initial_height_leaves_space_for_taskbar(self):
        area=self.w.screen().availableGeometry()
        self.assertLessEqual(self.w.height(),min(740,area.height()-40))
    def test_internal_play_does_not_launch_system_player(self):
        from unittest.mock import patch
        from PyQt6.QtCore import QUrl
        path=Path(self.tmp.name)/'sample.mp4';path.write_bytes(b'placeholder')
        c=E.defaults();c['prompt']='Test';job=E.job_create(self.w.output,c);job.update(status='已完成',files=[str(path)]);E.save_job(job);self.w.selected_id=job['id'];self.w.refresh_history()
        with patch.object(self.w,'chosen_file',return_value=str(path)),patch.object(self.w,'open_path') as external,patch.object(self.w.player,'play'):
            self.w.play();external.assert_not_called();self.assertEqual(self.w.player.source(),QUrl.fromLocalFile(str(path.resolve())))
        self.w.player.pause();source=self.w.player.source();self.w.toggle_language();self.assertEqual(self.w.player.source(),source)
        with patch.object(self.w,'open_path') as external:
            self.w.play_external();external.assert_called_once();self.assertEqual(Path(external.call_args.args[0]),path.resolve())
    def test_reference_frame_adds_thumbnail_and_persists_across_language(self):
        from PyQt6.QtGui import QImage,QColor
        p=Path(self.tmp.name)/'frame.png';im=QImage(80,60,QImage.Format.Format_RGB32);im.fill(QColor('blue'));im.save(str(p))
        self.w.on_event('reference_frame',str(p));picker=self.w.pickers['images']
        self.assertEqual(picker.paths,[str(p)]);self.assertFalse(picker.list.item(0).icon().isNull())
        self.w.toggle_language();self.assertEqual(self.w.pickers['images'].paths,[str(p)])
        self.assertEqual(json.loads((Path(self.tmp.name)/'settings.json').read_text('utf-8'))['config']['images'],[str(p)])
    def test_reference_frame_cancel_and_full_list_do_not_start_worker(self):
        from unittest.mock import patch
        with patch.object(self.w,'choose_frame_source',return_value='local'),patch('modern_app.QFileDialog.getOpenFileName',return_value=('', '')),patch.object(self.w,'start_worker') as worker:
            self.w.extract_reference();worker.assert_not_called()
        self.w.pickers['images'].paths=['example.png']*9
        with patch.object(self.w,'info'),patch('modern_app.QFileDialog.getOpenFileName') as dialog:
            self.w.extract_reference();dialog.assert_not_called()
    def test_completed_choices_exclude_missing_and_unfinished(self):
        c=E.defaults();c['prompt']='A blue ball';j=E.job_create(self.w.output,c)
        p=Path(j['folder'])/'result.mp4';p.write_bytes(b'example')
        j['files']=[str(p),str(p.parent/'missing.mp4')];j['status']='已完成';E.save_job(j)
        choices=self.w.completed_video_choices();self.assertEqual(len(choices),1);self.assertEqual(Path(choices[0][0]),p.resolve());self.assertIn('A blue ball',choices[0][1])
        j['status']='已提交';E.save_job(j);self.assertEqual(self.w.completed_video_choices(),[])
    def test_completed_source_never_opens_file_browser(self):
        from unittest.mock import patch
        p=Path(self.tmp.name)/'video.mp4';p.write_bytes(b'example')
        with patch.object(self.w,'choose_frame_source',return_value='tasks'),patch.object(self.w,'choose_completed_video',return_value=str(p)),patch('modern_app.QFileDialog.getOpenFileName') as browser,patch.object(self.w,'start_worker') as worker:
            self.w.extract_reference();browser.assert_not_called();worker.assert_called_once()
    def test_enum_wheel_does_not_change_value_but_dropdown_still_selects(self):
        from PyQt6.QtCore import Qt,QPoint,QPointF
        from PyQt6.QtGui import QWheelEvent
        from PyQt6.QtWidgets import QComboBox
        for combo in self.w.findChildren(QComboBox):
            combo.setCurrentIndex(0);combo.setFocus()
            event=QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(0,0),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
            APP.sendEvent(combo,event);self.assertEqual(combo.currentIndex(),0)
            combo.setCurrentIndex(1);self.assertEqual(combo.currentIndex(),1)
    def test_reset_defaults_preserves_user_content(self):
        w=self.w;w.prompt.setPlainText('Keep my prompt');w.controls['server'].setText('http://localhost:8188');w.controls['sampler'].setCurrentIndex(2);w.controls['steps'].setText('31')
        w.pickers['images'].paths=['example.png'];w.reset_parameters();w.capture()
        self.assertEqual(w.config['sampler'],'euler');self.assertEqual(int(w.config['steps']),8);self.assertEqual(w.config['prompt'],'Keep my prompt');self.assertEqual(w.config['images'],['example.png']);self.assertEqual(w.config['server'],'http://localhost:8188')
    def test_task_selection_switches_preview_without_play(self):
        from PyQt6.QtCore import QUrl
        jobs=[]
        for name in ['first','second']:
            path=Path(self.tmp.name)/(name+'.mp4');path.write_bytes(b'placeholder');c=E.defaults();c['prompt']=name;j=E.job_create(self.w.output,c);j.update(status='已完成',files=[str(path)]);E.save_job(j);jobs.append((j,path))
        for j,path in jobs:
            self.w.selected_id=j['id'];self.w.refresh_history();self.assertEqual(self.w.player.source(),QUrl.fromLocalFile(str(path.resolve())))
        jobs[1][0]['files']=[];E.save_job(jobs[1][0]);self.w.refresh_history();self.assertTrue(self.w.player.source().isEmpty())
    def test_editor_draft_survives_language_and_undo(self):
        editor=self.w.editor;editor.clips=[dict(id='a',path='example.mp4',duration=8.,start=0.,end=8.)];editor.selected=0;editor.refresh();editor.cursor=3.;editor.split();self.assertEqual(len(editor.clips),2);editor.undo_change();self.assertEqual(len(editor.clips),1);editor.save()
        self.w.toggle_language();self.assertEqual(len(self.w.editor.clips),1);self.assertEqual(self.w.editor.clips[0]['end'],8.)
    def test_enhance_first_use_cancel_preserves_draft(self):
        from unittest.mock import patch
        self.w.prompt.setPlainText('一个人走进庭院')
        with patch.object(self.w,'configure_enhancer',return_value=None) as configure,patch.object(self.w,'start_worker') as worker:
            self.w.enhance_prompt();configure.assert_called_once();worker.assert_not_called()
        self.assertEqual(self.w.prompt.toPlainText(),'一个人走进庭院')
    def test_enhancement_apply_can_be_undone(self):
        from unittest.mock import patch
        from PyQt6.QtWidgets import QDialog
        self.w.prompt.setPlainText('Original story')
        with patch('modern_app.EnhancementReview') as review:
            review.return_value.exec.return_value=QDialog.DialogCode.Accepted;review.return_value.result_text='Enhanced story'
            self.w.review_enhancement(dict(draft='Original story',result='Enhanced story'))
        self.assertEqual(self.w.prompt.toPlainText(),'Enhanced story');self.w.prompt.undo();self.assertEqual(self.w.prompt.toPlainText(),'Original story')
        self.assertEqual(len(list((Path(self.tmp.name)/'prompt_history').glob('*.json'))),1)
    def test_changing_output_preserves_old_tasks_and_remembers_roots(self):
        c=E.defaults();c['prompt']='old';old=E.job_create(self.w.output,c);self.w.refresh_history();self.assertIn(old['id'],self.w.jobs)
        new=Path(self.tmp.name)/'new-output';new.mkdir();self.w.set_output(new);self.assertIn(old['id'],self.w.jobs)
        fresh=E.job_create(new,c);self.w.refresh_history();self.assertIn(fresh['id'],self.w.jobs)
        other=Window(self.tmp.name);self.assertIn(old['id'],other.jobs);self.assertIn(fresh['id'],other.jobs);other.close();other.deleteLater()
    def test_round_corners_are_applied(self):self.assertIn('border-radius:12px',self.w.styleSheet())

if __name__=='__main__':unittest.main(verbosity=2)
