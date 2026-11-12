import unittest,tempfile,threading
from pathlib import Path
import edit_engine as X
import engine as E

class EditingTests(unittest.TestCase):
    def test_split_is_non_destructive_and_preserves_duration(self):
        clips=[dict(id='a',path='a.mp4',duration=10.,start=2.,end=8.)]
        split=X.split_clip(clips,0,4.)
        self.assertEqual(len(split),2);self.assertEqual(X.total_duration(split),6.);self.assertEqual(clips[0]['end'],8.)
        self.assertNotEqual(split[0]['id'],split[1]['id'])
        with self.assertRaises(ValueError):X.split_clip(clips,0,2.)
    def test_caption_roundtrip_and_invalid_times(self):
        cues=[dict(start=.1,end=1.234,text='你好\nHello')]
        self.assertEqual(X.parse_srt(X.srt_text(cues)),cues)
        with self.assertRaises(ValueError):X.srt_text([dict(start=2,end=1,text='bad')])
        with self.assertRaises(ValueError):X.srt_text(cues,.5)
    def test_empty_export_rejected(self):
        with self.assertRaises(ValueError):X.validate_clips([])
    def test_cancel_stops_subprocess(self):
        import sys
        flag=threading.Event();flag.set()
        with self.assertRaises(X.Cancelled):X.run([sys.executable,'-c','import time;time.sleep(20)'],flag)

if __name__=='__main__':unittest.main()
