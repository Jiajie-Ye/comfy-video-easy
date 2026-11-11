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
    def test_round_corners_are_applied(self):self.assertIn('border-radius:12px',self.w.styleSheet())

if __name__=='__main__':unittest.main(verbosity=2)
