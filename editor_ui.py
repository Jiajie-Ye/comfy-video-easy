"""A compact, single-track editor. Source videos are never modified."""
import copy,json,threading,uuid
from pathlib import Path
from PyQt6.QtCore import Qt,QUrl,pyqtSignal,QObject,QSize,QRectF,QPoint,QMimeData,QTimer
from PyQt6.QtGui import QPainter,QColor,QPen,QPixmap,QDrag,QImage
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QDoubleSpinBox,QComboBox,QSlider,QScrollArea,QDialog,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox)
from PyQt6.QtMultimedia import QMediaPlayer,QAudioOutput,QVideoSink
import engine as E
import edit_engine as X

class SafeCombo(QComboBox):
    def wheelEvent(self,event):event.ignore()

class Events(QObject):
    progress=pyqtSignal(str)
    done=pyqtSignal(str,object)

class PreviewSurface(QWidget):
    """Keep the last decoded image while a new source loads; invalid frames never blank it."""
    def __init__(self):
        super().__init__();self.image=QImage();self.setMinimumSize(240,160)
    def show_frame(self,frame):
        if not frame.isValid():return
        image=frame.toImage()
        if not image.isNull():self.image=image;self.update()
    def clear(self):self.image=QImage();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),Qt.GlobalColor.black)
        if not self.image.isNull():
            size=self.image.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
            p.drawImage(QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height()),self.image)

class Timeline(QWidget):
    MIME='application/x-comfy-video-clip'
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.setFixedHeight(100);self.setMouseTracking(True);self.setAcceptDrops(True);self.drag=None;self.drag_index=None;self.drop_slot=None
    def boxes(self):
        total=X.total_duration(self.editor.clips);scale=max(40,(self.width()-16)/max(total,.01));x=8.;result=[]
        for c in self.editor.clips:
            width=(c['end']-c['start'])*scale;result.append((round(x),max(1,round(x+width)-round(x))));x+=width
        return result
    def refresh(self):self.setMinimumWidth(max(600,round(X.total_duration(self.editor.clips)*40)+16));self.update()
    def draw_clip(self,p,index,x,width,y=27):
        c=self.editor.clips[index];p.setBrush(QColor('#bcd7ff' if index==self.editor.selected else '#e2edff'));p.setPen(QPen(QColor('#4087e8' if index==self.editor.selected else '#c3d8f3'),2));p.drawRoundedRect(QRectF(x+1,y,max(1,width-4),48),8,8)
        p.save();p.setClipRect(QRectF(x+3,y,max(1,width-8),48));p.setPen(QColor('#234c82'));name=p.fontMetrics().elidedText(f'{index+1}. '+Path(c['path']).stem,Qt.TextElideMode.ElideRight,max(1,width-14));p.drawText(x+7,y+20,name);p.drawText(x+7,y+39,f"{c['end']-c['start']:.2f}s");p.restore()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor('#f5f8ff'));offset=0
        for i,((x,w),c) in enumerate(zip(self.boxes(),self.editor.clips)):
            p.setPen(QColor('#557197'));p.drawText(x,18,f'{offset:.1f}s');p.save()
            if i==self.drag_index:p.setOpacity(.25)
            self.draw_clip(p,i,x,w);p.restore()
            if i==self.editor.selected:
                ratio=max(0,min(1,(self.editor.cursor-c['start'])/(c['end']-c['start'])));px=x+round(w*ratio);p.setPen(QPen(QColor('#2168d0'),2));p.drawLine(px,21,px,84)
            offset+=c['end']-c['start']
        if self.drop_slot is not None:
            boxes=self.boxes();x=boxes[self.drop_slot][0] if self.drop_slot<len(boxes) else sum(boxes[-1]);p.setPen(QPen(QColor('#1672eb'),4));p.drawLine(x,22,x,86)
        if not self.editor.clips:p.setPen(QColor('#66758b'));p.drawText(18,55,self.editor.t('先导入视频，然后在这里选择、拖动片段','Import videos, then select and drag clips here'))
    def hit(self,x):
        for i,(left,width) in enumerate(self.boxes()):
            if x<left+width:return i
        return max(0,len(self.editor.clips)-1)
    def insertion_slot(self,x):
        for i,(left,width) in enumerate(self.boxes()):
            if x<left+width/2:return i
        return len(self.editor.clips)
    def drag_pixmap(self,index):
        width=self.boxes()[index][1];pix=QPixmap(width,54);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setOpacity(.9);self.draw_clip(p,index,0,width,2);p.end();return pix
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.editor.busy or not self.editor.clips:return
        self.drag=(self.hit(event.position().x()),event.position().toPoint())
    def mouseMoveEvent(self,event):
        if not self.drag or not event.buttons() & Qt.MouseButton.LeftButton:return
        index,point=self.drag
        if (event.position().toPoint()-point).manhattanLength()<10:return
        self.drag=None;self.editor.pause();self.drag_index=index;drag=QDrag(self);mime=QMimeData();mime.setData(self.MIME,self.editor.clips[index]['id'].encode());drag.setMimeData(mime);drag.setPixmap(self.drag_pixmap(index));drag.setHotSpot(QPoint(max(0,point.x()-self.boxes()[index][0]),max(0,min(53,point.y()-25))));self.update()
        drag.exec(Qt.DropAction.MoveAction);self.drag_index=None;self.drop_slot=None;self.update()
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        index,_=self.drag;self.drag=None;x,width=self.boxes()[index];c=self.editor.clips[index];self.editor.select(index);self.editor.seek_source(c['start']+max(0,min(1,(event.position().x()-x)/width))*(c['end']-c['start']))
    def dragEnterEvent(self,event):
        if event.source() is self and not self.editor.busy and event.mimeData().hasFormat(self.MIME):event.acceptProposedAction()
    def dragMoveEvent(self,event):
        if event.source() is not self:return
        self.drop_slot=self.insertion_slot(event.position().x());self.update();event.acceptProposedAction()
        area=self.parentWidget().parentWidget()
        if isinstance(area,QScrollArea):
            x=self.mapTo(area.viewport(),event.position().toPoint()).x();bar=area.horizontalScrollBar()
            if x<35:bar.setValue(bar.value()-25)
            elif x>area.viewport().width()-35:bar.setValue(bar.value()+25)
    def dragLeaveEvent(self,event):self.drop_slot=None;self.update();event.accept()
    def dropEvent(self,event):
        if event.source() is not self or self.drag_index is None:return
        old=self.drag_index;slot=self.insertion_slot(event.position().x());new=slot-(1 if slot>old else 0);self.drop_slot=None;self.drag_index=None;self.editor.reorder(old,new);event.acceptProposedAction();self.update()

class Editor(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.t=window.t;self.clips=[];self.cues=[];self.selected=-1;self.cursor=0.;self.busy=False;self.undo=[];self.cancel=threading.Event();self.pending=None;self.preview_only=False;self.continuous=False;self.loading=False;self.seek_target=None;self.scrub_value=None;self.playback_revision=0
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
        self.video=PreviewSurface();self.sink=QVideoSink(self);self.sink.videoFrameChanged.connect(self.frame);self.player.setVideoSink(self.sink);left.addWidget(self.video)
        playback=QHBoxLayout();playback.addWidget(self.button('播放 / 暂停','Play / pause',self.play));self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.valueChanged.connect(self.scrub);self.seek.sliderReleased.connect(self.finish_scrub);playback.addWidget(self.seek,1);self.time=window.label('00:00','muted');playback.addWidget(self.time);left.addLayout(playback)
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
        self.scrub_timer=QTimer(self);self.scrub_timer.setSingleShot(True);self.scrub_timer.setInterval(60);self.scrub_timer.timeout.connect(self.flush_scrub)
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
        self.scrub_timer.stop();self.scrub_value=None;self.pause();self.timeline.refresh();total=X.total_duration(self.clips);self.seek.blockSignals(True);self.seek.setRange(0,round(total*1000));self.seek.blockSignals(False);self.total.setText(self.t(f'{len(self.clips)} 个片段 · 总长 {total:.2f} 秒',f'{len(self.clips)} clips · {total:.2f} seconds'));self.cue_count.setText(self.t(f'{len(self.cues)} 条字幕',f'{len(self.cues)} captions'))
        if self.clips:self.select(min(max(self.selected,0),len(self.clips)-1))
        else:
            self.loading=True;self.selected=-1;self.pending=None;self.seek_target=None;self.player.stop();self.player.setSource(QUrl());self.video.clear();self.clip_name.setText(self.t('请先添加视频','Add videos first'));self.time.setText('0.00 / 0.00s');self.seek.setValue(0)
    def locate(self,seconds):
        total=X.total_duration(self.clips);seconds=max(0,min(seconds,total));offset=0.
        for i,c in enumerate(self.clips):
            duration=c['end']-c['start']
            if seconds<offset+duration or i==len(self.clips)-1:return i,c['start']+min(duration,max(0,seconds-offset))
            offset+=duration
        return -1,0.
    def update_time(self):
        if self.selected<0:return
        c=self.clips[self.selected];prefix=sum(x['end']-x['start'] for x in self.clips[:self.selected]);value=prefix+max(0,min(c['end']-c['start'],self.cursor-c['start']))
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True);self.seek.setValue(round(value*1000));self.seek.blockSignals(False)
        self.time.setText(f'{value:.2f} / {X.total_duration(self.clips):.2f}s');self.timeline.update()
    def select(self,index,autoplay=False,source_time=None):
        if not 0<=index<len(self.clips):return
        self.scrub_timer.stop();self.scrub_value=None;self.playback_revision+=1
        previous_status=self.player.mediaStatus();at_source_end=self.player.duration()>0 and self.player.position()>=self.player.duration()-100
        self.loading=True;self.player.pause();self.continuous=autoplay;self.selected=index;c=self.clips[index];self.start.setValue(c['start']);self.end.setValue(c['end']);self.clip_name.setText(f'{index+1}. '+Path(c['path']).name);self.cursor=c['start'] if source_time is None else max(c['start'],min(source_time,c['end']));self.update_time()
        # Decode just before the exclusive out-point when the playhead is at the end.
        target=min(self.cursor,max(c['start'],c['end']-.04));self.pending=target;self.seek_target=target;self.preview_only=not autoplay;self.audio.setMuted(not autoplay)
        url=QUrl.fromLocalFile(c['path'])
        if self.player.source()!=url or at_source_end or previous_status in (QMediaPlayer.MediaStatus.EndOfMedia,QMediaPlayer.MediaStatus.InvalidMedia):
            self.player.stop();self.player.setSource(QUrl());self.player.setSource(url)
        elif previous_status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia,QMediaPlayer.MediaStatus.BufferingMedia,QMediaPlayer.MediaStatus.StalledMedia):
            self.pending=None;self.player.setPosition(round(target*1000));self.loading=False
        if Path(c['path']).is_file():self.player.play()
    def media_status(self,status):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia) and self.pending is not None:
            target=self.pending;self.pending=None;self.player.setPosition(round(target*1000));self.loading=False
        if status==QMediaPlayer.MediaStatus.EndOfMedia and self.continuous and not self.loading:self.advance()
    def frame(self,frame):
        if self.selected<0 or self.loading or not frame.isValid():return
        # QVideoFrame timestamps may include a stream offset (e.g. 166 ms of
        # B-frame delay). They are not the QMediaPlayer seek clock. Accept the
        # decoder's valid frame instead of waiting forever for an exact timestamp.
        self.seek_target=None
        self.video.show_frame(frame)
        if self.preview_only:self.preview_only=False;self.player.pause();self.audio.setMuted(False)
    def position(self,ms):
        if self.selected<0 or self.loading or self.scrub_value is not None or self.seek.isSliderDown():return
        c=self.clips[self.selected]
        if self.continuous:
            self.cursor=max(c['start'],min(ms/1000,c['end']));self.update_time()
            if self.cursor>=c['end']-.015:self.advance()
        elif self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState and not self.preview_only:
            self.cursor=max(c['start'],min(ms/1000,c['end']));self.update_time()
    def advance(self):
        if not self.continuous:return
        self.continuous=False
        if self.selected+1<len(self.clips):
            # Do not replace a Media Foundation source inside its position/end callback.
            # Defer until the decoder returns; a revision cancels stale transitions.
            revision=self.playback_revision;index=self.selected+1
            QTimer.singleShot(0,lambda:self.select(index,True) if revision==self.playback_revision else None)
        else:self.player.pause();self.cursor=self.clips[-1]['end'];self.update_time()
    def seek_source(self,seconds):
        if self.selected<0:return
        self.select(self.selected,False,seconds)
    def seek_global(self,seconds):
        index,source=self.locate(seconds)
        if index>=0:self.select(index,False,source)
    def scrub(self,ms):
        self.pause();self.scrub_value=ms/1000;index,source=self.locate(self.scrub_value)
        if index>=0:
            self.selected=index;self.cursor=source;c=self.clips[index];self.start.setValue(c['start']);self.end.setValue(c['end']);self.clip_name.setText(f'{index+1}. '+Path(c['path']).name);self.update_time()
        self.scrub_timer.start()
    def flush_scrub(self):
        if self.scrub_value is None:return
        value=self.scrub_value;self.scrub_value=None;self.seek_global(value)
    def finish_scrub(self):self.scrub_timer.stop();self.scrub_value=self.seek.value()/1000;self.flush_scrub()
    def play(self):
        if self.selected<0:return
        if self.continuous:self.pause();return
        pending_scrub=self.scrub_value;self.scrub_timer.stop();self.scrub_value=None;c=self.clips[self.selected]
        if self.cursor>=c['end']-.04:
            self.select(self.selected+1 if self.selected+1<len(self.clips) else 0,True)
        elif pending_scrub is not None or self.player.source()!=QUrl.fromLocalFile(c['path']):
            self.select(self.selected,True,self.cursor)
        else:
            # Resume an already-positioned decoder without issuing the same seek again.
            self.preview_only=False;self.continuous=True;self.audio.setMuted(False);self.player.play()
    def pause(self):self.playback_revision+=1;self.continuous=False;self.preview_only=False;self.player.pause()
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
