"""Qt desktop UI; the tested generation engine remains shared with version 0.1."""
from __future__ import annotations
import argparse, copy, json, os, re, sys, threading, time, traceback
from pathlib import Path
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QUrl, QTimer, QLocale, QTranslator, QLibraryInfo, QSize
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut, QImageReader, QPixmap, QIcon
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,
    QLabel,QPushButton,QTextEdit,QLineEdit,QComboBox,QSpinBox,QCheckBox,QListWidget,QListWidgetItem,
    QStackedWidget,QScrollArea,QFileDialog,QMessageBox,QProgressBar,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QSizePolicy,QDialog,QDialogButtonBox,QSlider)
if sys.platform=='win32':os.environ.setdefault('QT_MEDIA_BACKEND','windows')
from PyQt6.QtMultimedia import QMediaPlayer,QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
import engine as E

VERSION='0.3.0'
STYLE='''
QWidget {font-family: "Segoe UI", "Microsoft YaHei UI";font-size:14px;color:#252525;background:#ffffff;}
QMainWindow {background:#ffffff;}
QFrame#sidebar, QFrame#sidebar QLabel {background:#f5f5f4;}
QLabel#brand {font-size:23px;font-weight:600;letter-spacing:-1px;}
QLabel#title {font-size:30px;font-weight:600;letter-spacing:-.5px;}
QLabel#section {font-size:16px;font-weight:600;}
QLabel#muted {color:#777774;font-size:13px;background:transparent;}
QLabel#eyebrow {color:#777774;font-size:12px;letter-spacing:1px;background:transparent;}
QLabel#connection {color:#777774;font-size:12px;background:transparent;}
QPushButton {background:#ffffff;border:1px solid #e3e3e0;border-radius:10px;padding:9px 15px;min-height:20px;font-weight:500;}
QPushButton:hover {background:#f1f1ee;border-color:#d4d4cf;}
QPushButton:pressed {background:#e5e5e0;}
QPushButton:focus {border:1px solid #8c8c82;}
QPushButton:disabled {background:#f3f3f1;color:#a8a8a2;border-color:#eaeae6;}
QPushButton#primary {background:#262624;color:white;border:1px solid #262624;border-radius:12px;padding:12px 24px;min-height:24px;}
QPushButton#primary:hover {background:#41413d;}
QPushButton#primary:disabled {background:#b6b6af;border-color:#b6b6af;color:#ffffff;}
QPushButton#nav {background:transparent;border:0;text-align:left;padding:12px 16px;border-radius:10px;font-size:15px;}
QPushButton#nav:hover {background:#eaeae6;}
QPushButton#nav:checked {background:#e7e7e2;color:#171716;font-weight:600;}
QPushButton#quiet {border:0;background:transparent;color:#686862;padding:6px 8px;font-size:12px;}
QPushButton#quiet:hover {background:#eeeee9;color:#252525;}
QPushButton#language {background:#f6f6f3;border:1px solid #e8e8e2;border-radius:16px;padding:6px 14px;}
QFrame#card {background:#fafaf8;border:1px solid #eaeae4;border-radius:14px;}
QFrame#card QLabel,QFrame#card QCheckBox {background:transparent;}
QTextEdit,QLineEdit,QComboBox,QSpinBox {background:#fbfbf9;border:1px solid #e3e3dc;border-radius:10px;padding:10px;selection-background-color:#d8ddd5;selection-color:#252525;}
QTextEdit {padding:16px;border-radius:14px;font-size:15px;}
QTextEdit:focus,QLineEdit:focus,QComboBox:focus,QSpinBox:focus {border-color:#9a9a90;background:#ffffff;}
QComboBox {padding-right:30px;min-height:22px;}
QSpinBox {padding-right:32px;min-height:22px;}
QSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:28px;border:0;border-top-right-radius:10px;background:#f0f0ec;}
QSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:28px;border:0;border-bottom-right-radius:10px;background:#f0f0ec;}
QSpinBox::up-button:hover,QSpinBox::down-button:hover {background:#e4e4de;}
QSpinBox::up-arrow {image:url(__UP__);width:12px;height:10px;}
QSpinBox::down-arrow {image:url(__DOWN__);width:12px;height:10px;}
QComboBox::drop-down {border:0;width:28px;}
QComboBox QAbstractItemView {background:white;border:1px solid #ddd;border-radius:8px;selection-background-color:#eeeee8;selection-color:#252525;outline:0;padding:6px;}
QCheckBox {spacing:9px;min-height:28px;}
QCheckBox::indicator {width:19px;height:19px;border:1px solid #c7c7bf;border-radius:6px;background:#fff;}
QCheckBox::indicator:checked {background:#343a32;border:1px solid #343a32;image:url(__CHECK__);}
QListWidget {background:transparent;border:0;outline:0;font-size:13px;}
QListWidget::item {padding:7px 8px;border-radius:7px;}
QListWidget::item:selected {background:#e7ebe3;color:#252525;}
QListWidget::item:hover {background:#f0f0ea;}
QScrollArea {border:0;background:#ffffff;}
QScrollBar:vertical {width:8px;background:transparent;margin:3px;}
QScrollBar::handle:vertical {background:#d7d7d0;border-radius:3px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:none;}
QTableWidget {border:1px solid #e5e5df;border-radius:12px;gridline-color:#eeeeea;outline:0;selection-background-color:#edf0e8;selection-color:#252525;}
QHeaderView::section {background:#f7f7f3;border:0;border-bottom:1px solid #e5e5df;padding:14px;text-align:left;color:#73736c;}
QTableWidget::item {padding:10px;border:0;}
QProgressBar {border:0;background:#eeeee8;height:3px;max-height:3px;border-radius:1px;}
QProgressBar::chunk {background:#596451;border-radius:1px;}
QToolTip {background:#292a27;color:#ffffff;border:0;padding:7px;}
QMessageBox {background:#ffffff;}
'''
NAMES=[('制作视频','Create video'),('我的任务','My tasks'),('末帧工具','Last frame'),('高级设置','Settings'),('使用指南','Guide')]
RATIO_EN={'横屏 16:9':'Landscape 16:9','竖屏 9:16':'Portrait 9:16','方形 1:1':'Square 1:1','竖图 2:3':'Portrait 2:3'}
STATUS={
 '准备中':'Preparing','提交中':'Submitting','已提交':'Submitted','已完成':'Completed','生成失败':'Failed',
 '处理未完成':'Needs attention','提交结果待确认':'Submission unconfirmed','测试未完成':'Test incomplete',
 '等待恢复':'Awaiting reconnection','服务器正在生成，请耐心等待…':'Generating on the server…',
 '正在确认任务状态…':'Checking task status…','服务器正在记录结果…':'Finalizing results…',
 '任务已提交，正在排队或生成。':'Task submitted. Waiting for the server…',
 '连接暂时中断，正在重新查询（不会重复提交）…':'Connection interrupted. Reconnecting without resubmitting…'}

class Bridge(QObject):
    event=pyqtSignal(str,object)

class Picker(QFrame):
    def __init__(self,app,key,zh,en,tag,limit,pattern):
        super().__init__();self.setObjectName('card');self.app=app;self.key=key;self.tag=tag;self.limit=limit;self.pattern=pattern
        self.paths=list(app.config[key]);v=QVBoxLayout(self);v.setContentsMargins(16,12,16,10);v.setSpacing(5)
        h=QHBoxLayout();h.addWidget(app.label(app.t(zh,en),'section'));h.addStretch();h.addWidget(app.button(app.t('+ 添加','+ Add'),self.add,'quiet'));v.addLayout(h)
        self.empty=app.label(app.t('未选择文件，点击添加','No files yet. Choose Add.'),'muted');v.addWidget(self.empty)
        self.list=QListWidget();self.list.setMaximumHeight(76);self.list.setMinimumHeight(42);self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.list.itemDoubleClicked.connect(self.preview);v.addWidget(self.list)
        if key=='images':
            self.list.setIconSize(QSize(88,66));self.list.setMinimumHeight(94);self.list.setMaximumHeight(184)
        h=QHBoxLayout()
        for name,fn in [(app.t('移除','Remove'),self.remove),('↑',lambda:self.move(-1)),('↓',lambda:self.move(1))]:h.addWidget(app.button(name,fn,'quiet'))
        h.addStretch();self.counter=app.label('','muted');h.addWidget(self.counter);v.addLayout(h);self.refresh()
    def refresh(self):
        self.list.clear()
        if self.key=='images':self.list.setFixedHeight(min(170,max(86,len(self.paths)*82+4)))
        for i,p in enumerate(self.paths):
            item=QListWidgetItem(f'<{self.tag} {i+1}>  {Path(p).name}');item.setToolTip(p);self.list.addItem(item)
            if self.key=='images':
                pix=self.image(p,176,132)
                if not pix.isNull():item.setIcon(QIcon(pix))
                else:item.setText(item.text()+self.app.t('（无法预览）',' (preview unavailable)'))
                item.setSizeHint(QSize(200,80))
        self.empty.setVisible(not self.paths);self.list.setVisible(bool(self.paths));self.counter.setText(f'{len(self.paths)} / {self.limit}')
    def add(self):
        files,_=QFileDialog.getOpenFileNames(self,self.app.t('选择参考素材','Choose reference files'),'',self.app.t('媒体文件','Media files')+f' ({self.pattern})')
        result=list(self.paths)
        for f in files:
            if f not in result:result.append(f)
        if len(result)>self.limit:self.app.info(self.app.t(f'最多选择 {self.limit} 个素材。',f'Choose up to {self.limit} files.'))
        self.paths=result[:self.limit];self.refresh()
    def remove(self):
        for row in sorted([self.list.row(i) for i in self.list.selectedItems()],reverse=True):self.paths.pop(row)
        self.refresh()
    def move(self,d):
        selected=self.list.selectedItems()
        if len(selected)!=1:return
        i=self.list.row(selected[0]);j=i+d
        if 0<=j<len(self.paths):self.paths[i],self.paths[j]=self.paths[j],self.paths[i];self.refresh();self.list.setCurrentRow(j)
    @staticmethod
    def image(path,width,height):
        reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
        if size.isValid():reader.setScaledSize(size.scaled(width,height,Qt.AspectRatioMode.KeepAspectRatio))
        return QPixmap.fromImage(reader.read())
    def preview(self,item):
        path=self.paths[self.list.row(item)]
        if self.key!='images':self.app.open_path(path);return
        pix=self.image(path,1400,1000)
        if pix.isNull():self.app.info(self.app.t('无法预览这张图片，请检查文件。','Cannot preview this image. Check the file.'));return
        dialog=QDialog(self);dialog.setWindowTitle(self.app.t('图片预览 — ','Image preview — ')+Path(path).name);dialog.resize(900,700)
        layout=QVBoxLayout(dialog);area=QScrollArea();area.setWidgetResizable(True);label=QLabel();label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        class PreviewLabel(QLabel):
            def resizeEvent(self,event):
                super().resizeEvent(event);self.setPixmap(pix.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        label=PreviewLabel();label.setMinimumSize(100,100);label.setAlignment(Qt.AlignmentFlag.AlignCenter);area.setWidget(label);layout.addWidget(area)
        layout.addWidget(self.app.label(Path(path).name,'muted',True));layout.addWidget(self.app.button(self.app.t('关闭','Close'),dialog.accept));dialog.exec()

class Window(QMainWindow):
    def __init__(self,data_dir):
        super().__init__();self.data=Path(data_dir);self.data.mkdir(parents=True,exist_ok=True)
        self.lang='zh';self.config=E.defaults();self.output=str(self.data/'视频作品');self.page=0;self.busy=False;self.stop=threading.Event()
        self.status_pair=('准备好开始创作了','Ready when you are');self.raw_status=None;self.connected=False
        self.tool_video='';self.tool_dir='';self.tool_result='';self.selected_id=None;self.jobs={};self.worker=None;self.qt_translator=None
        try:
            old=json.loads((self.data/'settings.json').read_text('utf-8'));self.config.update(old.get('config',{}));self.output=old.get('output',self.output);self.lang=old.get('language','zh')
        except (OSError,ValueError):pass
        if self.lang not in ('zh','en'):self.lang='zh'
        self.bridge=Bridge();self.bridge.event.connect(self.on_event)
        self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.audio.setVolume(.7);self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self.update_playback);self.player.durationChanged.connect(self.update_playback);self.player.playbackStateChanged.connect(self.update_playback);self.player.errorOccurred.connect(self.playback_error)
        area=self.screen().availableGeometry();width=min(1220,area.width()-40);height=min(740,area.height()-80)
        self.setMinimumSize(min(960,width),min(560,height));self.resize(width,height);self.move(area.x()+20,area.y()+20)
        self.build();QShortcut(QKeySequence('Ctrl+Return'),self,activated=self.generate);QShortcut(QKeySequence('Alt+L'),self,activated=self.toggle_language)
    def t(self,zh,en):return zh if self.lang=='zh' else en
    def label(self,text,style='',wrap=False):
        w=QLabel(text);w.setTextFormat(Qt.TextFormat.PlainText);w.setWordWrap(wrap)
        if style:w.setObjectName(style)
        return w
    def button(self,text,fn,style=''):
        b=QPushButton(text);b.setCursor(Qt.CursorShape.PointingHandCursor);b.clicked.connect(lambda checked=False:fn())
        if style:b.setObjectName(style)
        return b
    def section(self,layout,title,subtitle=None):
        layout.addWidget(self.label(title,'section'))
        if subtitle:layout.addWidget(self.label(subtitle,'muted',True))
    def build(self):
        app=QApplication.instance()
        if self.qt_translator:app.removeTranslator(self.qt_translator)
        self.qt_translator=QTranslator()
        if self.lang=='zh':
            self.qt_translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath));app.installTranslator(self.qt_translator)
        self.setWindowTitle(self.t('AI 视频助手','AI Video Assistant')+' '+VERSION)
        self.setStyleSheet(STYLE.replace('__CHECK__',str(E.resource('check.svg')).replace('\\','/')).replace('__UP__',E.resource('arrow_up.svg').as_posix()).replace('__DOWN__',E.resource('arrow_down.svg').as_posix()))
        old=self.takeCentralWidget()
        if old:old.deleteLater()
        root=QWidget();self.setCentralWidget(root);outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(208);s=QVBoxLayout(sidebar);s.setContentsMargins(16,28,16,18);s.setSpacing(7)
        s.addWidget(self.label('AI Video','brand'));s.addWidget(self.label(self.t('你的私人创作空间','Your creative workspace'),'muted'));s.addSpacing(28)
        self.nav=[]
        for i,(zh,en) in enumerate(NAMES):
            b=self.button(self.t(zh,en),lambda i=i:self.navigate(i),'nav');b.setCheckable(True);self.nav.append(b);s.addWidget(b)
        s.addStretch();s.addWidget(self.label(self.t('服务器连接','SERVER CONNECTION'),'eyebrow'))
        self.connection=self.label(self.t('● 已连接','● Connected') if self.connected else self.t('○ 尚未检查','○ Not checked'),'connection');s.addWidget(self.connection)
        self.check=self.button(self.t('检查连接','Check connection'),self.check_connection);s.addWidget(self.check)
        s.addSpacing(12);s.addWidget(self.label('ComfyUI  /  Desktop','muted'));s.addWidget(self.label('v'+VERSION,'muted'));outer.addWidget(sidebar)
        content=QWidget();c=QVBoxLayout(content);c.setContentsMargins(32,25,32,18);c.setSpacing(18);outer.addWidget(content,1)
        top=QHBoxLayout();self.title=self.label('','title');top.addWidget(self.title);top.addStretch();self.language=self.button('EN  /  中文',self.toggle_language,'language');self.language.setToolTip(self.t('切换到英文 · Alt+L','Switch to Chinese · Alt+L'));top.addWidget(self.language);c.addLayout(top)
        self.subtitle=self.label('','muted',True);c.addWidget(self.subtitle)
        self.stack=QStackedWidget();c.addWidget(self.stack,1);self.controls={};self.pickers={}
        for builder in [self.create_page,self.history_page,self.tools_page,self.settings_page,self.guide_page]:
            page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(0,4,8,8);layout.setSpacing(18);builder(layout);layout.addStretch()
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.stack.addWidget(scroll)
        self.progress=QProgressBar();self.progress.setTextVisible(False);self.progress.setRange(0,0);c.addWidget(self.progress)
        foot=QHBoxLayout();self.status=self.label('','muted',True);foot.addWidget(self.status,1);self.run=self.button(self.t('开始生成  ↗','Generate video  ↗'),self.generate,'primary');foot.addWidget(self.run);c.addLayout(foot)
        self.navigate(self.page);self.sync_busy();self.refresh_history();self.update_status();self.update_playback()
    def navigate(self,i):
        self.page=i
        if i!=1:self.player.pause()
        self.stack.setCurrentIndex(i);self.title.setText(self.t(*NAMES[i]))
        subtitles=[('把想法写下来，让画面开始发生。','Describe your idea. Bring it to life.'),('每一次创作，都有迹可循。','Your generations, settings and results in one place.'),('将视频的最后一帧，留给下一个镜头。','Keep the final frame for your next shot.'),('按你的创作习惯，调整每一处细节。','Fine-tune your generation preferences.'),('从第一段视频开始。','Start with your first video.')]
        self.subtitle.setText(self.t(*subtitles[i]))
        for n,b in enumerate(self.nav):b.setChecked(n==i)
    def combo(self,key,options):
        w=QComboBox()
        for value,label in options:w.addItem(label,value)
        index=next((i for i in range(w.count()) if str(w.itemData(i))==str(self.config[key])),0);w.setCurrentIndex(index);self.controls[key]=w;return w
    def entry(self,key):
        w=QLineEdit(str(self.config[key]));self.controls[key]=w;return w
    def checkbox(self,key,zh,en):
        w=QCheckBox(self.t(zh,en));w.setChecked(bool(self.config[key]));self.controls[key]=w;return w
    def create_page(self,v):
        row=QHBoxLayout();row.setSpacing(28);left=QVBoxLayout();right=QVBoxLayout();row.addLayout(left,3);row.addLayout(right,2);v.addLayout(row)
        self.section(left,self.t('你想创造怎样的画面？','What would you like to create?'))
        self.prompt=QTextEdit();self.prompt.setAcceptRichText(False);self.prompt.setPlainText(self.config['prompt']);self.prompt.setMinimumHeight(235)
        self.prompt.setPlaceholderText(self.t('用英文描述场景、人物与动作…\n对白可以直接写中文。\n\n使用 <Picture 1> 引用第一张图片。','Describe the scene, characters and action…\nChinese dialogue can stay in Chinese.\n\nUse <Picture 1> for your first image.'));left.addWidget(self.prompt)
        tools=QHBoxLayout();tools.addWidget(self.button(self.t('试试示例','Try an example'),self.example,'quiet'));tools.addStretch();tools.addWidget(self.label('Ctrl + Enter','muted'));left.addLayout(tools)
        options=QHBoxLayout();a=QVBoxLayout();b=QVBoxLayout();a.addWidget(self.label(self.t('时长','Duration'),'muted'));duration=QSpinBox();duration.setRange(1,15);duration.setSingleStep(1);duration.setSuffix(self.t(' 秒',' seconds'));duration.setValue(int(float(self.config['seconds'])));duration.setToolTip(self.t('滚动鼠标滚轮、点击上下箭头，或输入 1–15 秒。','Use the mouse wheel, arrow buttons, or enter 1–15 seconds.'));self.controls['seconds']=duration;a.addWidget(duration);b.addWidget(self.label(self.t('画面比例','Aspect ratio'),'muted'));b.addWidget(self.combo('ratio',[(x,self.t(x,RATIO_EN[x])) for x in E.RATIOS]));options.addLayout(a);options.addLayout(b);left.addLayout(options)
        left.addSpacing(8);left.addWidget(self.checkbox('fixed','固定一采种子','Keep first-pass seed'));left.addWidget(self.checkbox('second','开启二次采样强化','Enable second-pass refinement'))
        left.addWidget(self.label(self.t('先生成一采，满意后可在“我的任务”中继续强化。','Start with a first pass. Refine a result you like from My tasks.'),'muted',True));left.addStretch()
        self.section(right,self.t('参考素材','References'),self.t('按列表顺序编号，双击文件可预览。','Numbered in list order. Double-click a file to preview.'))
        for key,zh,en,tag,limit,pattern in [('images','图片','Images','Picture',9,'*.png *.jpg *.jpeg *.webp *.bmp'),('audios','音频','Audio','Audio',3,'*.mp3 *.wav *.flac *.m4a *.ogg *.mp4'),('videos','视频 · 2–15 秒','Video · 2–15 seconds','Video',3,'*.mp4 *.mov *.mkv *.avi *.webm *.m4v')]:
            picker=Picker(self,key,zh,en,tag,limit,pattern);self.pickers[key]=picker;right.addWidget(picker)
        right.addWidget(self.checkbox('video_audio','同时参考视频原声','Use reference video sound'));right.addStretch()
        save=QHBoxLayout();save.addWidget(self.label(self.t('保存到','Save to'),'muted'));self.output_edit=QLineEdit(self.output);save.addWidget(self.output_edit,1);save.addWidget(self.button(self.t('更改','Change'),self.choose_output));v.addLayout(save)
    def example(self):
        if self.prompt.toPlainText().strip() and not self.confirm(self.t('替换当前描述为示例？','Replace your current prompt with the example?')):return
        self.prompt.setPlainText('A cinematic medium shot in a quiet courtyard. The camera slowly pushes in. A person looks at the camera and says in Mandarin Chinese: “大家好，欢迎来到我的视频！” Natural daylight, clear dialogue, light wind, no background music.')
    def choose_output(self):
        p=QFileDialog.getExistingDirectory(self,self.t('选择保存文件夹','Choose output folder'),self.output_edit.text())
        if p:self.output_edit.setText(p);self.output=p;self.refresh_history()
    def settings_page(self,v):
        cols=QHBoxLayout();cols.setSpacing(28);v.addLayout(cols);first=QVBoxLayout();second=QVBoxLayout();cols.addLayout(first,1);cols.addLayout(second,1)
        def field(layout,zh,en,key,options=None):
            layout.addWidget(self.label(self.t(zh,en),'muted'));layout.addWidget(self.combo(key,[(x,str(x)) for x in options]) if options else self.entry(key))
        self.section(first,self.t('一采 · 快速探索','First pass · Explore'))
        field(first,'像素规模（MP）','Resolution (MP)','megapixels',[.1,.2,.4,.6,.8,1.,1.5,2.])
        field(first,'采样步数','Sampling steps','steps');field(first,'去噪强度','Denoise strength','denoise');field(first,'种子','Seed','seed')
        field(first,'采样器','Sampler','sampler',['euler','heun','dpmpp_2m']);field(first,'调度器','Scheduler','scheduler',['beta','normal','simple','karras'])
        field(first,'参考图尺寸策略','Reference image sizing','ref_size',['max','match'])
        first.addWidget(self.label(self.t('max 保留更多参考细节，match 通常更快。','max preserves more reference detail; match is usually faster.'),'muted',True));first.addStretch()
        self.section(second,self.t('二采 · 进一步打磨','Second pass · Refine'))
        field(second,'像素规模（MP）','Resolution (MP)','second_mp',[.2,.4,.6,.8,1.,1.5,2.])
        field(second,'采样步数','Sampling steps','second_steps');field(second,'去噪强度','Denoise strength','second_denoise');field(second,'种子','Seed','second_seed')
        second.addWidget(self.checkbox('second_fixed','固定二采种子','Keep second-pass seed'))
        field(second,'缩放算法','Resize method','resize',['lanczos','bicubic','nvidia_rtx_vsr'])
        second.addWidget(self.label(self.t('默认 4 步、0.2 去噪。二采效果请与原片对比。','Defaults: 4 steps, 0.2 denoise. Compare the refined result with the first pass.'),'muted',True));second.addStretch()
        self.section(v,self.t('服务器','Server'));v.addWidget(self.entry('server'));v.addWidget(self.label(self.t('填写你自己的 ComfyUI 地址；支持本机、局域网或 Tailscale。','Enter your own ComfyUI URL: local, LAN, or Tailscale.'),'muted'))
    def history_page(self,v):
        v.setSpacing(10)
        h=QHBoxLayout();h.addWidget(self.label(self.t('最近的创作','Recent creations'),'section'));h.addStretch();h.addWidget(self.button(self.t('刷新','Refresh'),self.refresh_history));v.addLayout(h)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels([self.t('时间','Created'),self.t('状态','Status'),self.t('实际一采种子','Actual first-pass seed')]);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(48);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setShowGrid(False);self.table.setMinimumHeight(120);self.table.setMaximumHeight(150);self.table.itemSelectionChanged.connect(self.select_job);v.addWidget(self.table)
        h=QHBoxLayout()
        for zh,en,fn in [('继续查询 / 下载','Resume / download',self.resume),('用这条做二采','Refine this result',self.refine),('载入参数','Load settings',self.load_job),('打开文件夹','Open folder',self.open_folder)]:h.addWidget(self.button(self.t(zh,en),fn))
        h.addStretch();self.play_button=self.button(self.t('播放视频','Play video'),self.play);self.frame_button=self.button(self.t('提取末帧','Extract last frame'),self.extract_result);h.addWidget(self.play_button);h.addWidget(self.frame_button);v.addLayout(h)
        lower=QHBoxLayout();left=QVBoxLayout();lower.addLayout(left,4)
        self.details=self.label(self.t('选择一条任务，查看参数与结果。','Select a task to see its settings and results.'),'muted',True);self.details.setMaximumHeight(110);self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);left.addWidget(self.details)
        self.files=QListWidget();self.files.setMinimumHeight(100);self.files.itemDoubleClicked.connect(lambda _:self.play());left.addWidget(self.files,1)
        self.preview_panel=QFrame();self.preview_panel.setObjectName('card');panel=QVBoxLayout(self.preview_panel);panel.setContentsMargins(12,10,12,10)
        heading=QHBoxLayout();heading.addWidget(self.label(self.t('视频预览','Video preview'),'section'));heading.addStretch();heading.addWidget(self.button(self.t('系统播放器 ↗','System player ↗'),self.play_external,'quiet'));panel.addLayout(heading)
        self.video_widget=QVideoWidget();self.video_widget.setMinimumSize(240,120);self.video_widget.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Expanding);self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio);panel.addWidget(self.video_widget,1);self.player.setVideoOutput(self.video_widget)
        self.media_note=self.label(Path(self.player.source().toLocalFile()).name if not self.player.source().isEmpty() else self.t('选择结果后点击“播放视频”','Select a result and choose Play video'),'muted',True);panel.addWidget(self.media_note)
        controls=QHBoxLayout();self.pause_button=self.button(self.t('播放','Play'),self.toggle_playback,'quiet');controls.addWidget(self.pause_button)
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.setRange(0,self.player.duration());self.seek.sliderMoved.connect(self.player.setPosition);controls.addWidget(self.seek,1);self.media_time=self.label('00:00 / 00:00','muted');controls.addWidget(self.media_time);panel.addLayout(controls)
        lower.addWidget(self.preview_panel,5);v.addLayout(lower,1)
    def update_playback(self,*_):
        if not hasattr(self,'seek'):return
        self.seek.setRange(0,self.player.duration());self.seek.setEnabled(self.player.isSeekable())
        if not self.seek.isSliderDown():self.seek.setValue(self.player.position())
        def stamp(ms):return f'{ms//60000:02d}:{ms//1000%60:02d}'
        self.media_time.setText(stamp(self.player.position())+' / '+stamp(self.player.duration()))
        self.pause_button.setText(self.t('暂停','Pause') if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState else self.t('播放','Play'))
    def playback_error(self,*_):
        self.media_note.setText(self.t('无法内嵌播放，请尝试右上角“系统播放器”。','Cannot play here. Try System player at the top right.'))
        self.media_note.setToolTip(self.player.errorString())
    def toggle_playback(self):
        if self.player.source().isEmpty():self.play()
        elif self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause()
        else:self.player.play()
    def play_external(self):
        p=self.player.source().toLocalFile() or self.chosen_file()
        if p:self.player.pause();self.open_path(p)
    def refresh_history(self):
        if not hasattr(self,'table'):return
        self.output=self.output_edit.text();self.jobs={};self.table.blockSignals(True);self.table.setRowCount(0)
        for f in sorted(Path(self.output).glob('*/task.json'),reverse=True)[:300]:
            try:
                j=json.loads(f.read_text('utf-8'));j['folder']=str(f.parent);self.jobs[j['id']]=j;r=self.table.rowCount();self.table.insertRow(r)
                for c,value in enumerate([j['created'],self.translate_status(j['status']),str(j['settings']['seed'])]):
                    item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,j['id']);self.table.setItem(r,c,item)
                if j['id']==self.selected_id:self.table.selectRow(r)
            except (ValueError,KeyError,OSError):continue
        self.table.blockSignals(False);self.select_job()
    def selected_job(self,notify=True):
        selected=self.table.selectionModel().selectedRows()
        if not selected:
            if notify:self.info(self.t('请先选择一条任务。','Please select a task first.'))
            return None
        return self.jobs.get(self.table.item(selected[0].row(),0).data(Qt.ItemDataRole.UserRole))
    def select_job(self):
        j=self.selected_job(False);self.files.clear()
        if not j:return
        self.selected_id=j['id'];c=j['settings']
        self.details.setText(self.t(f"一采种子 {c['seed']}    二采种子 {c['second_seed']}\n{c['seconds']} 秒 · {c['megapixels']} MP\n{c['prompt']}",f"First-pass seed {c['seed']}    Second-pass seed {c['second_seed']}\n{c['seconds']} seconds · {c['megapixels']} MP\n{c['prompt']}"))
        for f in j.get('files',[]):
            name=Path(f).name
            if self.lang=='en':name=name.replace('一采_','First pass — ').replace('二采_','Second pass — ')
            item=QListWidgetItem(name);item.setData(Qt.ItemDataRole.UserRole,f);self.files.addItem(item)
        if self.files.count():self.files.setCurrentRow(self.files.count()-1)
    def chosen_file(self):
        item=self.files.currentItem()
        if not item:self.info(self.t('请选择一个已下载的视频。','Choose a downloaded video first.'));return None
        return item.data(Qt.ItemDataRole.UserRole)
    def play(self):
        p=self.chosen_file()
        if p:
            if not Path(p).is_file():self.info(self.t('视频文件不存在，请重新下载。','Video file is missing. Download it again.'));return
            self.player.setSource(QUrl.fromLocalFile(str(Path(p).resolve())));self.media_note.setText(Path(p).name);self.player.play()
            self.stack.widget(1).ensureWidgetVisible(self.preview_panel)
    def open_folder(self):
        j=self.selected_job()
        if j:self.open_path(j['folder'])
    def load_job(self):
        if self.busy:return
        j=self.selected_job()
        if j:
            self.capture();self.config=copy.deepcopy(j['settings']);self.config['fixed']=True;self.config['second_fixed']=True;self.page=0;self.build()
    def refine(self):
        if self.busy:return
        j=self.selected_job()
        if not j:return
        if j['status']!='已完成' or not j.get('uploaded'):self.info(self.t('请选择已经完成的任务，或先继续下载。','Select a completed task, or resume its download first.'));return
        try:
            self.capture();current=self.typed_config();c=copy.deepcopy(j['settings']);c.update(fixed=True,second=True)
            for key in ['second_mp','second_steps','second_denoise','second_fixed','second_seed','resize']:c[key]=current[key]
            c=E.concrete_settings(c)
        except Exception as exc:self.error(exc);return
        if self.confirm(self.t(f"使用此任务的素材、Prompt 和一采种子 {c['seed']} 继续强化？\n缓存失效时会重新计算一采。",f"Refine using this task's references, prompt and seed {c['seed']}?\nThe first pass may run again if its cache has expired.")):self.start_job(c,j['uploaded'],j['profile'])
    def resume(self):
        if self.busy:return
        j=self.selected_job()
        if j and j.get('prompt_id'):self.start_worker(lambda:self.monitor(j))
    def tools_page(self,v):
        card=QFrame();card.setObjectName('card');box=QVBoxLayout(card);box.setContentsMargins(26,24,26,24);box.setSpacing(18)
        self.section(box,self.t('提取最后一帧','Extract the final frame'),self.t('在本机处理，无需连接服务器。图片不会覆盖已有文件。','Runs locally, without a server connection. Existing images are never overwritten.'))
        box.addWidget(self.label(self.t('视频文件','Video file'),'muted'));h=QHBoxLayout();self.video_edit=QLineEdit(self.tool_video);self.video_edit.setPlaceholderText(self.t('选择一个视频…','Choose a video…'));h.addWidget(self.video_edit,1);h.addWidget(self.button(self.t('选择视频','Choose video'),self.choose_video));box.addLayout(h)
        box.addWidget(self.label(self.t('图片保存位置','Image destination'),'muted'));h=QHBoxLayout();self.dir_edit=QLineEdit(self.tool_dir);self.dir_edit.setPlaceholderText(self.t('留空则保存到视频旁边','Leave blank to save beside the video'));h.addWidget(self.dir_edit,1);h.addWidget(self.button(self.t('选择文件夹','Choose folder'),self.choose_tool_dir));box.addLayout(h)
        h=QHBoxLayout();self.extract_button=self.button(self.t('提取最后一帧','Extract last frame'),self.extract,'primary');h.addWidget(self.extract_button);h.addStretch();box.addLayout(h)
        self.frame_label=self.label(self.tool_result or self.t('提取后的 PNG 将显示在这里。','Your extracted PNG will appear here.'),'muted',True);box.addWidget(self.frame_label);box.addWidget(self.button(self.t('打开图片','Open image'),lambda:self.open_path(self.tool_result) if self.tool_result else None));v.addWidget(card)
    def choose_video(self):
        f,_=QFileDialog.getOpenFileName(self,self.t('选择视频','Choose video'),'','Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.ts)')
        if f:self.video_edit.setText(f)
    def choose_tool_dir(self):
        p=QFileDialog.getExistingDirectory(self,self.t('选择图片保存文件夹','Choose image folder'))
        if p:self.dir_edit.setText(p)
    def extract_result(self):
        p=self.chosen_file()
        if p:self.video_edit.setText(p);self.dir_edit.setText(str(Path(p).parent));self.navigate(2);self.extract()
    def extract(self):
        if self.busy:return
        self.capture();video=Path(self.tool_video)
        if not video.is_file():self.info(self.t('请先选择有效的视频文件。','Choose an existing video file first.'));return
        folder=self.tool_dir or str(video.parent)
        def work():self.emit('pair',('正在提取最后一帧…','Extracting the last frame…'));self.emit('frame',str(E.extract_last_frame(video,folder)))
        self.start_worker(work)
    def guide_page(self,v):
        sections=[('01  开始创作','01  Create your first video','在高级设置填写服务器地址，点击“检查连接”。添加参考素材，填写英文画面描述和中文对白，然后开始生成。默认 10 秒、一采 8 步。','Set your server URL in Settings and choose Check connection. Add references, describe your scene, then generate. Chinese dialogue can stay in Chinese. Defaults: 10 seconds and 8 first-pass steps.'),
        ('02  参考素材编号','02  Reference numbering','图片、音频、视频分别使用 <Picture 1>、<Audio 1>、<Video 1>。编号跟随列表顺序，移动素材会改变编号。最多 9 张图片，音频和视频各 3 段。视频长度为 2–15 秒。','Use <Picture 1>, <Audio 1> and <Video 1> to reference each list. Reordering files changes the numbers. Up to 9 images, 3 audio clips and 3 videos. Reference videos must be 2–15 seconds long.'),
        ('03  满意之后，再做二采','03  Refine a result you like','先不开二采，生成几条候选。在“我的任务”中选择满意的一条，点击“用这条做二采”。程序自动沿用那条任务的实际种子、Prompt 和素材。二采采用当前高级设置。','Generate candidates with refinement off. Select your favorite in My tasks, then choose Refine this result. Its actual seed, prompt and references are reused. Refinement uses your current second-pass settings.'),
        ('04  断线与任务恢复','04  Reconnect and resume','关闭窗口不会停止已提交的服务器任务。恢复连接后，在“我的任务”选择“继续查询 / 下载”。程序不会自动重复提交，也不会停止其他人的任务。','Closing the app does not stop a submitted server task. After reconnecting, use Resume / download in My tasks. The app will not resubmit automatically or interrupt other users.'),
        ('05  文件保存与升级','05  Files and upgrades','EXE 旁的“我的视频数据”保存设置、任务和视频。升级时将新版 EXE 放回原文件夹，保留这个数据文件夹。请保留原始参考素材。固定种子不保证跨模型版本完全复现。','Settings, tasks and videos live in 我的视频数据 beside the EXE. When upgrading, place the new EXE in the same folder and keep that data folder. Keep your original reference files. Fixed seeds do not guarantee identical output across model versions.'),
        ('06  中英文切换','06  Switch languages','点击右上角 EN / 中文，即刻切换界面语言。也可使用 Alt+L。Prompt、文件、参数与正在执行的任务不会被清空；下次启动沿用所选语言。','Use EN / 中文 in the top-right corner, or Alt+L. Your prompt, references, settings and running task are preserved. Your language preference is remembered next time.')]
        for zh,en,bodyzh,bodyen in sections:self.section(v,self.t(zh,en));v.addWidget(self.label(self.t(bodyzh,bodyen),'',True));v.addSpacing(12)
    def capture(self):
        for key,w in self.controls.items():
            self.config[key]=w.isChecked() if isinstance(w,QCheckBox) else (w.value() if isinstance(w,QSpinBox) else (w.currentData() if isinstance(w,QComboBox) else w.text()))
        self.config['prompt']=self.prompt.toPlainText()
        for key,w in self.pickers.items():self.config[key]=list(w.paths)
        self.output=self.output_edit.text();self.tool_video=self.video_edit.text();self.tool_dir=self.dir_edit.text()
    def typed_config(self):
        c=copy.deepcopy(self.config)
        for k,value in E.defaults().items():
            if isinstance(value,bool):c[k]=bool(c[k])
            elif isinstance(value,int):c[k]=int(c[k])
            elif isinstance(value,float):c[k]=float(c[k])
        return c
    def save_preferences(self):
        self.capture();E.atomic_json(self.data/'settings.json',{'config':self.config,'output':self.output,'language':self.lang})
    def toggle_language(self):
        self.capture();self.lang='en' if self.lang=='zh' else 'zh';self.build();self.save_preferences()
    def translate_status(self,value):
        if self.lang=='zh':return value
        if value in STATUS:return STATUS[value]
        if value.startswith('排队中'):return 'Queued · position '+value.split()[-1]
        if value.startswith('正在上传 '):return value.replace('正在上传 ','Uploading ',1)
        if value.startswith('正在下载一采'):return 'Downloading first-pass video…'
        if value.startswith('正在下载二采'):return 'Downloading refined video…'
        return value
    def update_status(self):self.status.setText(self.translate_status(self.raw_status) if self.raw_status is not None else self.t(*self.status_pair))
    def emit(self,name,value):self.bridge.event.emit(name,value)
    def sync_busy(self):
        self.run.setEnabled(not self.busy);self.check.setEnabled(not self.busy);self.extract_button.setEnabled(not self.busy);self.progress.setVisible(self.busy)
        self.run.setText(self.t('处理中…','Working…') if self.busy else self.t('开始生成  ↗','Generate video  ↗'))
    def start_worker(self,fn):
        if self.busy:return
        self.busy=True;self.stop.clear();self.sync_busy()
        def run():
            try:fn()
            except Exception as exc:
                try:
                    with (self.data/'error.log').open('a',encoding='utf-8') as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S')+'\n'+traceback.format_exc()+'\n')
                except OSError:pass
                self.emit('error',str(exc))
            finally:self.emit('idle',None)
        self.worker=threading.Thread(target=run,daemon=True);self.worker.start()
    def on_event(self,name,value):
        if name=='status':self.raw_status=value
        elif name=='pair':self.raw_status=None;self.status_pair=value
        elif name=='connected':self.connected=True;self.connection.setText(self.t('● 已连接','● Connected'))
        elif name=='refresh':self.refresh_history()
        elif name=='frame':self.tool_result=value;self.frame_label.setText(value);self.raw_status=None;self.status_pair=('末帧已保存，可以打开图片了。','Last frame saved. Your image is ready.')
        elif name=='completed':self.selected_id=value['id'];self.refresh_history();self.raw_status=None;self.status_pair=('视频已保存，可以播放或继续强化。','Video saved. Play it or refine it further.')
        elif name=='error':self.raw_status=None;self.status_pair=('处理未完成，记录已保留。','Needs attention. Your task record has been kept.');self.error(value)
        elif name=='idle':self.busy=False;self.sync_busy()
        self.update_status()
    def check_connection(self):
        if self.busy:return
        self.capture();url=self.config['server']
        def work():
            self.emit('pair',('正在检查服务器和模型…','Checking server and models…'));client=E.Client(url);client.json('/system_stats',timeout=15);schema=client.json('/object_info',timeout=60);p=E.model_profile()
            for typ,key,name in [('UNETLoader','unet_name','model'),('CLIPLoader','clip_name','clip'),('VAELoader','vae_name','video_vae'),('VAELoader','vae_name','audio_vae'),('LoraLoaderModelOnly','lora_name','lora')]:
                spec=schema[typ]['input']['required'][key];options=spec[0] if isinstance(spec[0],list) else spec[1].get('options',[])
                if p[name] not in options:raise RuntimeError('Model unavailable: '+p[name])
            self.emit('connected',None);self.emit('pair',('已连接，服务器和模型可用。','Connected. Server and models are ready.'))
        self.start_worker(work)
    def generate(self):
        if self.busy:return
        try:
            self.capture();c=E.concrete_settings(self.typed_config())
            if not self.output.strip():raise ValueError(self.t('请选择保存文件夹。','Choose an output folder.'))
            self.controls['seed'].setText(str(c['seed']));self.controls['second_seed'].setText(str(c['second_seed']));self.save_preferences()
        except Exception as exc:self.error(exc);return
        self.start_job(c)
    def start_job(self,c,reuse=None,profile=None):
        try:j=E.job_create(self.output,c,profile)
        except Exception as exc:self.error(exc);return
        self.selected_id=j['id'];self.refresh_history();self.navigate(1)
        def work():
            try:E.prepare_and_submit(j,self.emit,reuse);self.emit('refresh',None);self.monitor(j)
            except Exception as exc:
                j['error']=str(exc)
                if j['status'] not in ('提交结果待确认','已提交','生成失败'):j['status']='处理未完成'
                E.save_job(j);self.emit('refresh',None);raise
        self.start_worker(work)
    def monitor(self,j):
        if E.monitor(j,self.emit,self.stop):self.emit('completed',j)
    def info(self,text):QMessageBox.information(self,self.t('提示','Information'),text)
    def confirm(self,text):
        m=QMessageBox(self);m.setWindowTitle(self.t('确认','Confirm'));m.setText(text);yes=m.addButton(self.t('继续','Continue'),QMessageBox.ButtonRole.AcceptRole);m.addButton(self.t('取消','Cancel'),QMessageBox.ButtonRole.RejectRole);m.exec();return m.clickedButton()==yes
    def error(self,exc):
        raw=str(exc);message=raw
        if self.lang=='en':
            translations=[('请先填写视频描述','Enter a video prompt before generating.'),('种子必须','Seeds must be whole numbers between 0 and 9007199254740991.'),('无法连接服务器','Cannot connect. Check your network and make sure the server is online.'),('素材不存在','A reference file is missing. Please select it again.'),('找不到素材','A reference file is missing. Please select it again.'),('参考视频需要','Reference videos must be 2–15 seconds long.'),('单个参考素材','Each reference file must be smaller than 500 MB.'),('没有音轨','A reference video has no audio track. Turn off reference video sound.'),('服务器生成失败','Generation failed on the server. Your task record has been kept.'),('服务器未找到','The server could not find this task. Its history may have been cleared.'),('缺少节点','A required node is missing on the server.'),('必须在','A numeric setting is outside its supported range.'),('提取末帧失败','Could not extract the final frame.'),('invalid literal','Please enter whole numbers for steps and seeds.'),('could not convert','Please enter valid numbers in Settings.')]
            message=next((en for zh,en in translations if zh in raw),'The operation could not be completed. Check your settings and connection.')
            if not re.search('[\u4e00-\u9fff]',raw) and message.startswith('The operation'):message=raw
        m=QMessageBox(self);m.setIcon(QMessageBox.Icon.Warning);m.setWindowTitle(self.t('需要检查','Needs attention'));m.setText(message)
        if message!=raw:m.setDetailedText(raw)
        m.addButton(self.t('知道了','OK'),QMessageBox.ButtonRole.AcceptRole);m.exec()
    def open_path(self,path):
        p=Path(path)
        if not p.exists():self.info(self.t('文件不存在，请检查保存位置。','File not found. Check its saved location.'));return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))
    def closeEvent(self,event):
        if self.busy and not self.confirm(self.t('服务器任务可能继续运行。关闭窗口会中断本机上传或下载，之后可从任务记录继续查询。现在关闭？','Server tasks may keep running. Local uploads or downloads will stop. You can resume from My tasks later. Close now?')):event.ignore();return
        try:self.save_preferences()
        except OSError:pass
        self.player.stop();self.stop.set();event.accept()

def self_test(folder,check_server=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);report={'version':VERSION,'checks':[]}
    try:
        video=folder/'self_test.mp4';r=E.run_media([E.ffmpeg_path(),'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=64x64:r=24:d=1','-c:v','libx264','-pix_fmt','yuv420p','-y',str(video)])
        if r.returncode:raise RuntimeError(r.stderr)
        report['checks'].append('bundled_ffmpeg');assert E.inspect_video(video)['streams'][0]['width']==64;report['checks'].append('bundled_ffprobe');assert E.extract_last_frame(video,folder).is_file();report['checks'].append('last_frame')
        app=QApplication.instance() or QApplication([]);w=Window(folder/'ui_data');w.prompt.setPlainText('Test prompt 中文');w.toggle_language();assert w.prompt.toPlainText()=='Test prompt 中文';report['checks'].append('qt_and_language_toggle')
        frames=[];w.video_widget.videoSink().videoFrameChanged.connect(lambda frame:frames.append(frame.isValid()))
        w.player.setSource(QUrl.fromLocalFile(str(video.resolve())));w.player.play();deadline=time.monotonic()+10
        while not any(frames) and time.monotonic()<deadline:app.processEvents();time.sleep(.02)
        assert any(frames),w.player.errorString() or 'No decoded video frame';report['checks'].append('embedded_video_decode');w.close()
        if check_server:report['server']=E.Client().json('/system_stats')['system']['comfyui_version']
        report['passed']=True
    except Exception:report['passed']=False;report['error']=traceback.format_exc()
    E.atomic_json(folder/'self_test_report.json',report);return 0 if report['passed'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--self-test');parser.add_argument('--check-server',action='store_true');args=parser.parse_args()
    if args.self_test:sys.exit(self_test(args.self_test,args.check_server))
    app=QApplication(sys.argv);app.setStyle('Fusion')
    base=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
    data=args.data_dir or str(base/'我的视频数据')
    try:
        Path(data).mkdir(parents=True,exist_ok=True);probe=Path(data)/'.write_check';probe.write_text('ok');probe.unlink()
    except OSError:
        data=QFileDialog.getExistingDirectory(None,'选择数据文件夹 / Choose a data folder')
        if not data:sys.exit(0)
    w=Window(data);w.show();sys.exit(app.exec())
