"""Image creation dialog, separate from video prompts and text-model settings."""
import json,threading
from pathlib import Path
from PyQt6.QtCore import Qt,QObject,pyqtSignal,QSize
from PyQt6.QtGui import QPixmap,QIcon,QImageReader
from PyQt6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QTextEdit,QCheckBox,QListWidget,QListWidgetItem,QFileDialog,QAbstractItemView,QLabel)
from enhancer_ui import SafeCombo
import engine as E
import image_service as I

def thumbnail(path,width=1200,height=1000):
    reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
    if size.isValid():reader.setScaledSize(size.scaled(width,height,Qt.AspectRatioMode.KeepAspectRatio))
    return QPixmap.fromImage(reader.read())

class ImageSettings(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.t=window.t;self.result_config=None;cfg=I.load_config(window.data)
        self.setWindowTitle(self.t('人物/场景图像生成 · 接口设置','Character / scene images · API settings'));self.resize(min(720,window.width()-40),min(510,window.height()-40));v=QVBoxLayout(self);form=QFormLayout();form.setSpacing(12);v.addLayout(form)
        self.kind=SafeCombo()
        for key,label in I.KINDS:self.kind.addItem(label,key)
        self.kind.setCurrentIndex(max(0,self.kind.findData(cfg['kind'])));form.addRow(self.t('图像接口格式','Image API type'),self.kind)
        self.url=QLineEdit(cfg['url']);self.url.setPlaceholderText('https://your-provider.example/v1');form.addRow('URL',self.url)
        self.key=QLineEdit(cfg['api_key']);self.key.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('API KEY',self.key)
        show=QCheckBox(self.t('显示密钥','Show key'));show.toggled.connect(lambda on:self.key.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password));form.addRow('',show)
        self.model=QLineEdit(cfg['model']);self.model.setPlaceholderText(self.t('填写支持图像输出的模型名称','Enter a model that supports image output'));form.addRow(self.t('模型名称','Model name'),self.model)
        v.addWidget(window.label(self.t('与提示词增强的配置分开保存。OpenAI 兼容接口需支持 images/generations；添加参考图时需支持 images/edits。Gemini 使用 generateContent 图像输出。','Saved separately from prompt enhancement. OpenAI-compatible APIs need images/generations, and images/edits for reference inputs. Gemini uses generateContent with image output.'),'muted',True))
        v.addWidget(window.label(self.t('生成时会将描述和所选参考图片发送到此接口。密钥使用 Windows 当前账号加密保存。','Generation sends the description and selected reference images to this API. The key is encrypted for this Windows account.'),'muted',True))
        self.error=window.label(self.t('原密钥无法解密，请重新填写。','Re-enter the key; it cannot be unlocked here.') if cfg.get('key_locked') else '','muted',True);v.addWidget(self.error);v.addStretch();row=QHBoxLayout();row.addStretch();row.addWidget(window.button(self.t('取消','Cancel'),self.reject));row.addWidget(window.button(self.t('保存设置','Save settings'),self.save,'primary'));v.addLayout(row)
    def save(self):
        c=dict(kind=self.kind.currentData(),url=self.url.text().strip(),model=self.model.text().strip(),api_key=self.key.text().strip())
        try:I.save_config(self.window.data,c)
        except Exception as exc:self.error.setText(str(exc));return
        self.result_config=c;self.accept()

class ImagePreview(QLabel):
    def __init__(self):
        super().__init__();self.original=QPixmap();self.setMinimumSize(280,200);self.setAlignment(Qt.AlignmentFlag.AlignCenter);self.setStyleSheet('background:#f5f8ff;border:1px solid #dce7f6;border-radius:12px;');self.setWordWrap(True)
    def show_image(self,path):self.original=thumbnail(path);self.update_pixmap()
    def update_pixmap(self):
        if not self.original.isNull():self.setPixmap(self.original.scaled(self.size()-QSize(12,12),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):super().resizeEvent(event);self.update_pixmap()

class ImageEvents(QObject):
    done=pyqtSignal(object,str)

class ImageCreator(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.t=window.t;self.data=window.data;self.result_path=None;self.busy=False;self.refs=[];self.latest_paths=set();self.last_error='';self.events=ImageEvents(self);self.events.done.connect(self.finished)
        self.setWindowTitle(self.t('人物/场景图像生成','Character / scene image generation'));self.resize(min(1060,window.width()-40),min(650,window.height()-40));v=QVBoxLayout(self);v.setContentsMargins(20,16,20,16)
        top=QHBoxLayout();top.addWidget(window.label(self.t('描述人物或场景，生成后再选择是否使用。','Describe a character or scene, then review before using.'),'muted',True));top.addStretch();self.settings=window.button(self.t('图像接口设置','Image API settings'),self.configure);top.addWidget(self.settings);v.addLayout(top)
        columns=QHBoxLayout();self.inputs=QWidget();left=QVBoxLayout(self.inputs);left.setContentsMargins(0,0,0,0);columns.addWidget(self.inputs,4);right=QVBoxLayout();columns.addLayout(right,5);v.addLayout(columns,1)
        left.addWidget(window.label(self.t('图像描述','Image description'),'section'));self.prompt=QTextEdit();self.prompt.setAcceptRichText(False);self.prompt.setPlaceholderText(self.t('例如：一位古代将军的人物设定图，正面、侧面、背面，保持服装和面容一致。\n或：黄昏时的古城战场，无人物。','Example: a character sheet of an ancient general, front, side and back views, with consistent face and outfit.'));left.addWidget(self.prompt,1)
        left.addWidget(window.label(self.t('参考图片（可选，按列表顺序）','Reference images (optional, in list order)'),'section'));self.references=QListWidget();self.references.setIconSize(QSize(56,42));self.references.setMaximumHeight(140);self.references.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);left.addWidget(self.references)
        row=QHBoxLayout();row.addWidget(window.button(self.t('添加图片','Add images'),self.add_local));row.addWidget(window.button(self.t('从当前素材选','From current references'),self.add_current));row.addWidget(window.button(self.t('移除','Remove'),self.remove));left.addLayout(row)
        left.addWidget(window.label(self.t('点击生成会上传描述和这里选中的参考图。','Generate sends your description and these selected reference images.'),'muted',True));self.generate_button=window.button(self.t('生成图片','Generate image'),self.generate,'primary');left.addWidget(self.generate_button)
        self.result_heading=window.label(self.t('历史结果','Previous results'),'section');right.addWidget(self.result_heading);self.preview=ImagePreview();self.preview.setText(self.t('生成的图片将在这里显示','Generated images will appear here'));right.addWidget(self.preview,1)
        self.results=QListWidget();self.results.setViewMode(QListWidget.ViewMode.IconMode);self.results.setIconSize(QSize(72,54));self.results.setMaximumHeight(95);self.results.currentItemChanged.connect(self.selected_result);self.results.itemDoubleClicked.connect(self.large_preview);right.addWidget(self.results)
        row=QHBoxLayout();row.addWidget(window.button(self.t('查看大图','View larger'),self.large_preview));row.addStretch();self.insert=window.button(self.t('加入参考图片','Add to references'),self.use_result,'primary');self.insert.setEnabled(False);row.addWidget(self.insert);right.addLayout(row)
        self.note=window.label(self.t('结果会保存在工作目录；支持查看最近的生成图片。','Results are saved in your workspace; recent images are shown below.'),'muted',True);v.addWidget(self.note)
        bottom=QHBoxLayout();self.error_details_button=window.button(self.t('查看错误详情','Error details'),self.show_error_details);self.error_details_button.hide();bottom.addWidget(self.error_details_button);bottom.addStretch();self.close_button=window.button(self.t('关闭','Close'),self.reject);bottom.addWidget(self.close_button);v.addLayout(bottom)
        try:
            draft=json.loads((self.data/'image_draft.json').read_text('utf-8'));self.prompt.setPlainText(draft.get('prompt',''));self.refs=[x for x in draft.get('references',[])[:9] if Path(x).is_file()]
        except (OSError,ValueError):pass
        self.refresh_refs()
        for path in sorted((self.data/'generated_images').glob('*.png'),key=lambda p:p.stat().st_mtime)[-20:]:self.add_result(str(path))
        if self.results.count():self.results.setCurrentRow(self.results.count()-1)
    def configure(self):
        if self.busy:return None
        d=ImageSettings(self.window)
        return d.result_config if d.exec()==QDialog.DialogCode.Accepted else None
    def save_draft(self):E.atomic_json(self.data/'image_draft.json',dict(prompt=self.prompt.toPlainText(),references=self.refs))
    def refresh_refs(self):
        self.references.clear()
        for i,path in enumerate(self.refs):item=QListWidgetItem(QIcon(thumbnail(path,112,84)),f'{i+1}. '+Path(path).name);item.setToolTip(path);self.references.addItem(item)
    def add_paths(self,paths):
        for path in paths:
            if path not in self.refs:
                if len(self.refs)>=9:self.note.setText(self.t('最多添加 9 张参考图。','At most 9 reference images.'));break
                self.refs.append(path)
        self.refresh_refs()
    def add_local(self):
        paths,_=QFileDialog.getOpenFileNames(self,self.t('选择参考图片','Choose reference images'),'','Images (*.png *.jpg *.jpeg *.webp *.bmp)');self.add_paths(paths)
    def add_current(self):
        d=QDialog(self);d.setWindowTitle(self.t('选择当前视频参考图片','Choose current video references'));d.resize(520,360);v=QVBoxLayout(d);listing=QListWidget();listing.setIconSize(QSize(72,54));listing.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection);v.addWidget(listing)
        for i,path in enumerate(self.window.pickers['images'].paths):
            item=QListWidgetItem(QIcon(thumbnail(path,144,108)),f'<Picture {i+1}> '+Path(path).name);item.setData(Qt.ItemDataRole.UserRole,path);listing.addItem(item)
        row=QHBoxLayout();row.addWidget(self.window.button(self.t('取消','Cancel'),d.reject));row.addWidget(self.window.button(self.t('添加选中图片','Add selected'),d.accept));v.addLayout(row)
        if d.exec()==QDialog.DialogCode.Accepted:self.add_paths([item.data(Qt.ItemDataRole.UserRole) for item in listing.selectedItems()])
    def remove(self):
        for row in sorted([self.references.row(i) for i in self.references.selectedItems()],reverse=True):self.refs.pop(row)
        self.refresh_refs()
    def generate(self):
        if self.busy:return
        prompt=self.prompt.toPlainText().strip()
        if not prompt:self.note.setText(self.t('请先填写图像描述。','Enter an image description first.'));return
        cfg=I.load_config(self.data)
        try:
            I.validate(cfg)
            if cfg.get('key_locked'):raise ValueError()
        except ValueError:
            cfg=self.configure()
            if cfg is None:return
        self.last_error='';self.error_details_button.hide();self.latest_paths=set();self.result_heading.setText(self.t('正在生成 · 下方为历史结果','Generating · previous results below'));self.save_draft();paths=list(self.refs);folder=self.data;self.busy=True;self.inputs.setEnabled(False);self.settings.setEnabled(False);self.insert.setEnabled(False);self.note.setText(self.t('正在生成图片，请稍候…','Generating an image, please wait…'))
        def work():
            try:self.events.done.emit(I.generate(cfg,prompt,paths,folder),'')
            except Exception as exc:self.events.done.emit([],str(exc) if isinstance(exc,I.ImageError) else self.t('无法生成或保存图片，请检查接口和工作目录。','Cannot generate/save image. Check your API and workspace.'))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def add_result(self,path):
        item=QListWidgetItem(QIcon(thumbnail(path,144,108)),str(self.results.count()+1));item.setData(Qt.ItemDataRole.UserRole,path);item.setToolTip(path);self.results.addItem(item)
    def finished(self,paths,error):
        self.busy=False;self.inputs.setEnabled(True);self.settings.setEnabled(True);self.latest_paths=set(paths);self.last_error=error;self.error_details_button.setVisible(bool(error))
        if error:
            try:E.atomic_json(self.data/'image_error.json',dict(error=error))
            except OSError:pass
        for path in paths:self.add_result(path)
        if paths:self.results.setCurrentRow(self.results.count()-1)
        self.insert.setEnabled(self.results.currentItem() is not None)
        if error:self.result_heading.setText(self.t('本次生成失败 · 下方为历史结果','Generation failed · previous results below'))
        self.note.setText((error.splitlines()[0]+'\n'+self.t('点击“查看错误详情”了解原因。右侧旧图片不是本次结果。','Choose Error details. The previous image is not a new result.')) if error else self.t('已保存。满意后点击“加入参考图片”；也可修改描述再次生成。','Saved. Choose Add to references, or revise the description and generate again.'))
    def selected_result(self,item,previous=None):
        self.insert.setEnabled(item is not None and not self.busy)
        if item:
            path=item.data(Qt.ItemDataRole.UserRole);self.preview.show_image(path);self.result_heading.setText(self.t('本次生成结果','New result') if path in self.latest_paths else self.t('历史结果','Previous result'))
    def show_error_details(self):
        if not self.last_error:return
        d=QDialog(self);d.setWindowTitle(self.t('图像生成错误详情','Image generation error details'));d.resize(680,330);layout=QVBoxLayout(d);text=QTextEdit();text.setReadOnly(True);text.setPlainText(self.last_error);layout.addWidget(text);layout.addWidget(self.window.button(self.t('关闭','Close'),d.accept));d.exec()
    def large_preview(self,*_):
        item=self.results.currentItem()
        if not item:return
        d=QDialog(self);d.resize(min(1050,self.window.screen().availableGeometry().width()-80),min(750,self.window.screen().availableGeometry().height()-100));v=QVBoxLayout(d);preview=ImagePreview();v.addWidget(preview);preview.show_image(item.data(Qt.ItemDataRole.UserRole));v.addWidget(self.window.button(self.t('关闭','Close'),d.accept));d.exec()
    def use_result(self):
        item=self.results.currentItem()
        if self.busy or not item:return
        path=item.data(Qt.ItemDataRole.UserRole);picker=self.window.pickers['images']
        if path not in picker.paths and len(picker.paths)>=picker.limit:self.note.setText(self.t('视频参考图片已满 9 张，请先移除一张。生成结果已保存。','Video references already contain 9 images. Remove one first; the result is saved.'));return
        if not Path(path).is_file():self.note.setText(self.t('图片文件不存在。','Image file is missing.'));return
        self.save_draft();self.result_path=path;self.accept()
    def reject(self):
        if self.busy:self.note.setText(self.t('正在等待图像接口返回，请稍候；超时后会恢复操作。','Waiting for the image API; controls will return after completion or timeout.'));return
        self.save_draft();super().reject()
    def closeEvent(self,event):
        if self.busy:self.reject();event.ignore()
        else:self.save_draft();event.accept()
