"""A compact, single-track editor. Source videos are never modified."""
import copy,json,threading,uuid
from pathlib import Path
from PyQt6.QtCore import Qt,QUrl,pyqtSignal,QObject,QSize
from PyQt6.QtGui import QPainter,QColor,QPen
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QDoubleSpinBox,QComboBox,QSlider,QScrollArea,QDialog,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox)
from PyQt6.QtMultimedia import QMediaPlayer,QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import engine as E
import edit_engine as X

class SafeCombo(QComboBox):
    def wheelEvent(self,event):event.ignore()

class Events(QObject):
    progress=pyqtSignal(str)
    done=pyqtSignal(str,object)

class Timeline(QWidget):
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.setFixedHeight(100);self.setMouseTracking(True);self.drag=None
    def boxes(self):
        x=8;result=[]
        for c in self.editor.clips:
            width=max(90,int((c['end']-c['start'])*20));result.append((x,width));x+=width+4
        return result
    def refresh(self):self.setMinimumWidth(max(600,sum(w+4 for _,w in self.boxes())+16));self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor('#f5f8ff'));offset=0
        for i,((x,w),c) in enumerate(zip(self.boxes(),self.editor.clips)):
            p.setPen(QColor('#557197'));p.drawText(x,18,f'{offset:.1f}s');p.setBrush(QColor('#bcd7ff' if i==self.editor.selected else '#e2edff'));p.setPen(QPen(QColor('#4087e8' if i==self.editor.selected else '#c3d8f3'),2));p.drawRoundedRect(x,27,w,48,8,8)
            p.setPen(QColor('#234c82'));p.drawText(x+7,47,f'{i+1}. '+Path(c['path']).stem[:max(4,w//9-4)]);p.drawText(x+7,66,f"{c['end']-c['start']:.2f}s")
            if i==self.editor.selected:
                ratio=max(0,min(1,(self.editor.cursor-c['start'])/(c['end']-c['start'])));px=x+int(w*ratio);p.setPen(QPen(QColor('#2168d0'),2));p.drawLine(px,21,px,84)
            offset+=c['end']-c['start']
        if not self.editor.clips:p.setPen(QColor('#66758b'));p.drawText(18,55,self.editor.t('先导入视频，然后在这里选择、拖动片段','Import videos, then select and drag clips here'))
    def hit(self,x):
        boxes=self.boxes()
        for i,(left,width) in enumerate(boxes):
            if left<=x<=left+width:return i
        return len(boxes)-1 if boxes and x>=boxes[-1][0] else 0
    def mousePressEvent(self,event):
        if self.editor.busy or not self.editor.clips:return
        i=self.hit(event.position().x());self.drag=(i,event.position().x());self.editor.select(i)
        x,w=self.boxes()[i];c=self.editor.clips[i];self.editor.seek_source(c['start']+max(0,min(1,(event.position().x()-x)/w))*(c['end']-c['start']))
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        i,x=self.drag;self.drag=None
        if abs(event.position().x()-x)>24:self.editor.reorder(i,self.hit(event.position().x()))

class Editor(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.t=window.t;self.clips=[];self.cues=[];self.selected=-1;self.cursor=0.;self.busy=False;self.undo=[];self.cancel=threading.Event();self.pending=None;self.preview_only=False;self.continuous=False
        self.project=window.data/'editing_project.json'
        try:
            data=json.loads(self.project.read_text('utf-8'));self.clips=data.get('clips',[]);self.cues=data.get('cues',[])
        except (OSError,ValueError):pass
        self.events=Events(self);self.events.progress.connect(self.progress);self.events.done.connect(self.finished)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio);self.audio.setVolume(.7)
        self.player.mediaStatusChanged.connect(self.media_status);self.player.positionChanged.connect(self.position);self.player.errorOccurred.connect(lambda *_:self.note.setText(self.t('无法预览该视频，请检查素材。','Cannot preview this video. Check the source.')))
        v=QVBoxLayout(self);v.setContentsMargins(0,0,0,0);v.setSpacing(12)
        self.body=QWidget();body=QVBoxLayout(self.body);body.setContentsMargins(0,0,0,0);body.setSpacing(12);v.addWidget(self.body)
        row=QHBoxLayout();row.addWidget(self.button('从任务添加','Add from tasks',self.add_tasks));row.addWidget(self.button('从本地添加','Add local videos',self.add_local));row.addWidget(self.button('撤销','Undo',self.undo_change));row.addStretch();row.addWidget(self.button('清空草稿','Clear draft',self.clear));body.addLayout(row)
        center=QHBoxLayout();left=QVBoxLayout();right=QVBoxLayout();center.addLayout(left,3);center.addLayout(right,2);body.addLayout(center)
        self.video=QVideoWidget();self.video.setMinimumSize(240,160);self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio);self.player.setVideoOutput(self.video);self.video.videoSink().videoFrameChanged.connect(self.frame);left.addWidget(self.video)
        playback=QHBoxLayout();playback.addWidget(self.button('播放 / 暂停','Play / pause',self.play));self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.sliderMoved.connect(lambda x:self.seek_source(x/1000));playback.addWidget(self.seek,1);self.time=window.label('00:00','muted');playback.addWidget(self.time);left.addLayout(playback)
        self.clip_name=window.label(self.t('选择时间轴上的片段','Select a clip on the timeline'),'section',True);right.addWidget(self.clip_name)
        self.start=QDoubleSpinBox();self.end=QDoubleSpinBox()
        for field in [self.start,self.end]:field.setDecimals(2);field.setRange(0,86400);field.setSingleStep(.1);field.setSuffix(' s')
        bounds=QHBoxLayout();bounds.addWidget(window.label(self.t('入点','In')));bounds.addWidget(self.start);bounds.addWidget(window.label(self.t('出点','Out')));bounds.addWidget(self.end);right.addLayout(bounds)
        trim=QHBoxLayout();trim.addWidget(self.button('此处作为入点','Set in here',lambda:self.set_boundary(True)));trim.addWidget(self.button('此处作为出点','Set out here',lambda:self.set_boundary(False)));right.addLayout(trim)
        tools=QHBoxLayout();tools.addWidget(self.button('应用裁剪','Apply trim',self.trim));tools.addWidget(self.button('在此分割','Split here',self.split));tools.addWidget(self.button('删除片段','Remove',self.remove));right.addLayout(tools)
        self.total=window.label('','muted',True);right.addWidget(self.total);right.addStretch()
        body.addWidget(window.label(self.t('时间轴 · 点击定位，左右拖动片段调整拼接顺序','Timeline · Click to seek; drag clips left or right to reorder'),'muted',True))
        self.timeline=Timeline(self);area=QScrollArea();area.setWidgetResizable(True);area.setFixedHeight(118);area.setWidget(self.timeline);body.addWidget(area)
        captions=QHBoxLayout();captions.addWidget(self.button('自动识别字幕','Auto captions',self.auto_captions));captions.addWidget(self.button('编辑字幕','Edit captions',self.edit_captions));captions.addWidget(self.button('导入 SRT','Import SRT',self.import_srt));self.cue_count=window.label('','muted');captions.addWidget(self.cue_count);captions.addStretch();body.addLayout(captions)
        export=QHBoxLayout();self.size=SafeCombo()
        for label,size in [('720p · 16:9',(1280,720)),('1080p · 16:9',(1920,1080)),('1080p · 9:16',(1080,1920)),('720p · 9:16',(720,1280))]:self.size.addItem(label,size)
        export.addWidget(self.size);self.burn=QCheckBox(self.t('字幕烧录进画面','Burn captions into video'));self.burn.setChecked(True);export.addWidget(self.burn);export.addStretch();export.addWidget(self.button('导出 MP4','Export MP4',self.export,'primary'));body.addLayout(export)
        footer=QHBoxLayout();self.note=window.label(self.t('草稿自动保存；不会修改原视频。','Draft saves automatically; source videos stay unchanged.'),'muted',True);footer.addWidget(self.note,1);self.cancel_button=self.button('取消处理','Cancel processing',self.cancel.set);self.cancel_button.hide();footer.addWidget(self.cancel_button);v.addLayout(footer)
        self.refresh()
    def button(self,zh,en,fn,style=''):return self.window.button(self.t(zh,en),fn,style)
    def save(self):
        if self.project is not None:E.atomic_json(self.project,dict(clips=self.clips,cues=self.cues))
    def snapshot(self):
        self.undo.append(copy.deepcopy((self.clips,self.cues)));self.undo=self.undo[-30:]
    def changed(self):
        if self.cues:self.cues=[];self.note.setText(self.t('片段已改变，请重新识别或导入字幕。','Clips changed. Regenerate or import captions.'))
        self.save();self.refresh()
    def refresh(self):
        self.timeline.refresh();self.total.setText(self.t(f'{len(self.clips)} 个片段 · 总长 {X.total_duration(self.clips):.2f} 秒',f'{len(self.clips)} clips · {X.total_duration(self.clips):.2f} seconds'));self.cue_count.setText(self.t(f'{len(self.cues)} 条字幕',f'{len(self.cues)} captions'))
        if self.clips:self.select(min(max(self.selected,0),len(self.clips)-1))
        else:self.selected=-1;self.player.stop();self.player.setSource(QUrl());self.clip_name.setText(self.t('请先添加视频','Add videos first'))
    def select(self,index,autoplay=False):
        if not 0<=index<len(self.clips):return
        self.continuous=False;self.selected=index;c=self.clips[index];self.start.setValue(c['start']);self.end.setValue(c['end']);self.clip_name.setText(f'{index+1}. '+Path(c['path']).name);self.cursor=c['start'];self.seek.setRange(round(c['start']*1000),round(c['end']*1000));self.timeline.update()
        self.pending=c['start'];self.preview_only=not autoplay;self.audio.setMuted(not autoplay)
        url=QUrl.fromLocalFile(c['path'])
        if self.player.source()!=url:self.player.stop();self.player.setSource(url)
        else:self.player.setPosition(round(c['start']*1000));self.pending=None
        if Path(c['path']).is_file():self.player.play()
    def media_status(self,status):
        if status==QMediaPlayer.MediaStatus.LoadedMedia and self.pending is not None:self.player.setPosition(round(self.pending*1000));self.pending=None
        if status==QMediaPlayer.MediaStatus.EndOfMedia and self.continuous:self.advance()
    def frame(self,frame):
        if self.preview_only and frame.isValid():self.preview_only=False;self.player.pause();self.audio.setMuted(False)
    def position(self,ms):
        if self.selected<0:return
        self.cursor=ms/1000
        if not self.seek.isSliderDown():self.seek.setValue(ms)
        c=self.clips[self.selected];prefix=sum(x['end']-x['start'] for x in self.clips[:self.selected]);self.time.setText(f'{prefix+max(0,self.cursor-c["start"]):.2f} / {X.total_duration(self.clips):.2f}s');self.timeline.update()
        if self.continuous and self.cursor>=c['end']-.03:self.advance()
    def advance(self):
        self.continuous=False
        if self.selected+1<len(self.clips):self.select(self.selected+1,True);self.continuous=True
        else:self.player.pause()
    def seek_source(self,seconds):
        if self.selected<0:return
        self.preview_only=False;self.continuous=False;self.player.pause();self.cursor=seconds;
        if self.pending is not None:self.pending=seconds
        self.player.setPosition(round(seconds*1000));self.timeline.update()
    def play(self):
        if self.selected<0:return
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause();self.continuous=False
        else:
            c=self.clips[self.selected]
            if self.cursor>=c['end']-.05:self.player.setPosition(round(c['start']*1000))
            self.preview_only=False;self.audio.setMuted(False);self.continuous=True;self.player.play()
    def pause(self):self.continuous=False;self.player.pause()
    def set_boundary(self,start):
        if self.selected>=0:(self.start if start else self.end).setValue(self.cursor)
    def trim(self):
        if self.selected<0:return
        c=self.clips[self.selected];a,b=self.start.value(),self.end.value()
        if not 0<=a<b<=c['duration']+.01:self.window.info(self.t('出点必须大于入点，且不能超出原片。','Out must be after In and within the source duration.'));return
        self.snapshot();c.update(start=a,end=min(b,c['duration']));self.changed()
    def split(self):
        if self.selected<0:return
        try:clips=X.split_clip(self.clips,self.selected,self.cursor)
        except ValueError as exc:self.window.info(str(exc));return
        self.snapshot();self.clips=clips;self.changed()
    def remove(self):
        if self.selected>=0:self.snapshot();self.clips.pop(self.selected);self.changed()
    def reorder(self,old,new):
        if old==new:return
        self.snapshot();c=self.clips.pop(old);self.clips.insert(new,c);self.selected=new;self.changed()
    def undo_change(self):
        if self.undo:self.clips,self.cues=self.undo.pop();self.save();self.refresh()
    def clear(self):
        if self.clips and self.window.confirm(self.t('清空剪辑草稿？原视频会保留，可撤销。','Clear this editing draft? Source files stay unchanged. You can undo.')):self.snapshot();self.clips=[];self.cues=[];self.changed()
    def add_local(self):
        files,_=QFileDialog.getOpenFileNames(self,self.t('选择视频，可多选','Choose videos'),'', 'Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)')
        if files:self.add_files(files)
    def add_tasks(self):
        choices=self.window.completed_video_choices();d=QDialog(self);d.setWindowTitle(self.t('从已完成任务添加，可多选','Add completed videos'));d.resize(700,440);v=QVBoxLayout(d)
        from PyQt6.QtWidgets import QListWidget,QListWidgetItem,QAbstractItemView
        listing=QListWidget();listing.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection);v.addWidget(listing)
        for path,label in choices:item=QListWidgetItem(label);item.setData(Qt.ItemDataRole.UserRole,path);listing.addItem(item)
        if not choices:v.addWidget(self.window.label(self.t('暂无已完成且已下载的视频。','No completed, downloaded videos available.'),'muted'))
        row=QHBoxLayout();row.addWidget(self.button('取消','Cancel',d.reject));row.addWidget(self.button('添加选中视频','Add selected',d.accept,'primary'));v.addLayout(row)
        if d.exec()==QDialog.DialogCode.Accepted:
            files=[i.data(Qt.ItemDataRole.UserRole) for i in listing.selectedItems()]
            if files:self.add_files(files)
    def add_files(self,files):self.work('import',lambda:[X.new_clip(f) for f in files])
    def work(self,kind,fn):
        if self.busy:return
        self.pause();self.busy=True;self.cancel.clear();self.body.setEnabled(False);self.cancel_button.show();self.window.language.setEnabled(False);self.note.setText(self.t('处理中，请稍候…','Working, please wait…'))
        def run():
            try:result=fn();self.events.done.emit(kind,result)
            except X.Cancelled:self.events.done.emit('cancel',None)
            except Exception as exc:self.events.done.emit('error',str(exc))
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
    def progress(self,text):self.note.setText(self.t('处理中：','Working: ')+text)
    def finished(self,kind,result):
        self.busy=False;self.body.setEnabled(True);self.cancel_button.hide();self.window.language.setEnabled(True)
        if kind=='import':self.snapshot();self.clips.extend(result);self.changed()
        elif kind=='captions':self.cues=result;self.save();self.refresh();self.note.setText(self.t('字幕识别完成，请点击编辑字幕校对。','Captions ready. Use Edit captions to review.') if result else self.t('未识别到语音，可手动添加字幕。','No speech recognized. You can add captions manually.'));return
        elif kind=='install':self.note.setText(self.t('字幕组件已就绪，请再次点击自动识别字幕。','Caption components ready. Choose Auto captions again.'));return
        elif kind=='export':self.note.setText(self.t('已导出：','Exported: ')+result);self.window.info(self.t('视频已导出：','Video exported: ')+result);return
        elif kind=='error':self.note.setText(self.t('处理未完成。','Operation failed.'));self.window.error(result);return
        elif kind=='cancel':self.note.setText(self.t('已取消，原视频未改变。','Cancelled. Sources unchanged.'));return
        self.note.setText(self.t('已保存草稿。','Draft saved.'))
    def auto_captions(self):
        if not self.clips:self.window.info(self.t('请先添加视频。','Add videos first.'));return
        root=self.window.data/'speech_components';exe,model=X.asr_paths(root)
        if not exe or not model.exists():
            if self.window.confirm(self.t('首次使用需下载约 160 MB 的本地语音识别组件和模型。完成后无需上传视频即可识别字幕。现在下载？','Download about 160 MB of local speech recognition components and a model? Your videos are not uploaded.')):self.work('install',lambda:X.install_asr(root,self.cancel,self.events.progress.emit))
            return
        clips=copy.deepcopy(self.clips)
        self.work('captions',lambda:X.recognize(clips,root,self.cancel,self.events.progress.emit,'auto'))
    def import_srt(self):
        path,_=QFileDialog.getOpenFileName(self,self.t('导入字幕','Import captions'),'','SRT (*.srt)')
        if not path:return
        try:
            cues=X.parse_srt(Path(path).read_text('utf-8-sig'));X.srt_text(cues,X.total_duration(self.clips));self.cues=cues;self.save();self.refresh()
        except Exception as exc:self.window.error(exc)
    def edit_captions(self):
        d=QDialog(self);d.setWindowTitle(self.t('编辑字幕 · 时间单位为秒','Edit captions · Times in seconds'));d.resize(760,440);v=QVBoxLayout(d);table=QTableWidget(len(self.cues),3);table.setHorizontalHeaderLabels([self.t('开始','Start'),self.t('结束','End'),self.t('字幕内容','Caption')]);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);v.addWidget(table)
        for i,c in enumerate(self.cues):
            for j,key in enumerate(['start','end','text']):table.setItem(i,j,QTableWidgetItem(str(c[key])))
        def add():
            i=table.rowCount();table.insertRow(i)
            for j,text in enumerate(['0','1','']):table.setItem(i,j,QTableWidgetItem(text))
        def remove():
            if table.currentRow()>=0:table.removeRow(table.currentRow())
        def save():
            try:
                cues=[dict(start=float(table.item(i,0).text()),end=float(table.item(i,1).text()),text=table.item(i,2).text()) for i in range(table.rowCount())];X.srt_text(cues,X.total_duration(self.clips));self.cues=cues;self.save();self.refresh();d.accept()
            except Exception as exc:self.window.error(exc)
        row=QHBoxLayout();row.addWidget(self.button('添加一行','Add row',add));row.addWidget(self.button('删除一行','Remove row',remove));row.addStretch();row.addWidget(self.button('取消','Cancel',d.reject));row.addWidget(self.button('保存字幕','Save captions',save,'primary'));v.addLayout(row);d.exec()
    def export(self):
        try:X.validate_clips(self.clips);X.srt_text(self.cues,X.total_duration(self.clips))
        except Exception as exc:self.window.error(exc);return
        path,_=QFileDialog.getSaveFileName(self,self.t('导出视频','Export video'),str(self.window.data/'剪辑成片.mp4'),'MP4 (*.mp4)')
        if not path:return
        if not path.lower().endswith('.mp4'):path+='.mp4'
        clips,cues=copy.deepcopy((self.clips,self.cues));size=self.size.currentData();burn=self.burn.isChecked()
        self.work('export',lambda:X.export_video(clips,path,size,cues,burn,self.events.progress.emit,self.cancel))
