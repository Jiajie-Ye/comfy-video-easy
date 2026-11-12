"""Provider configuration and review dialogs for prompt enhancement."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QTextEdit,QComboBox,QSpinBox,QCheckBox,QTabWidget,QWidget,QFileDialog,QLabel)
import prompt_enhancer as P

class SafeCombo(QComboBox):
    def wheelEvent(self,event):event.ignore()

class EnhancementSettings(QDialog):
    def __init__(self,window,config):
        super().__init__(window);self.window=window;self.t=window.t;self.result_config=None
        self.setWindowTitle(self.t('剧本提示词增强 · 设置','Prompt enhancement · Settings'));self.resize(min(800,window.width()-40),min(620,window.height()-60));v=QVBoxLayout(self);v.setContentsMargins(20,18,20,18)
        tabs=QTabWidget();v.addWidget(tabs,1);api=QWidget();form=QFormLayout(api);form.setSpacing(12);reference=QWidget();ref=QVBoxLayout(reference);tabs.addTab(api,self.t('模型接口','Model API'));tabs.addTab(reference,self.t('参考格式文本','Reference format'))
        self.kind=SafeCombo()
        for value,label in P.KINDS:self.kind.addItem(label,value)
        self.kind.setCurrentIndex(max(0,self.kind.findData(config['kind'])));form.addRow(self.t('接口格式','API type'),self.kind)
        self.url=QLineEdit(config['url']);form.addRow('URL',self.url)
        self.key=QLineEdit(config['api_key']);self.key.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('API KEY',self.key)
        visible=QCheckBox(self.t('显示密钥','Show key'));visible.toggled.connect(lambda on:self.key.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password));form.addRow('',visible)
        self.model=QLineEdit(config['model']);self.model.setPlaceholderText(self.t('填写服务商提供的准确模型名称','Enter the exact model name from your provider'));form.addRow(self.t('模型名称','Model name'),self.model)
        self.limit=QSpinBox();self.limit.setRange(512,32768);self.limit.setSingleStep(512);self.limit.setValue(int(config['max_tokens']));form.addRow(self.t('输出长度上限','Max output tokens'),self.limit)
        self.hint=window.label('','muted',True);form.addRow(self.hint);self.kind.currentIndexChanged.connect(self.update_hint);self.update_hint()
        notice=self.t('增强会将剧情、参考格式文本、时长与素材数量发送到所填接口，不发送素材文件。API KEY 使用 Windows 当前账号加密保存；换电脑需重新填写。','Enhancement sends your story, reference format, duration and media counts to this API, not media files. The API key is encrypted for this Windows account; enter it again on another computer.')
        if config.get('key_locked'):notice=self.t('原密钥无法在当前账号解密，请重新填写。\n','The saved key cannot be unlocked here. Enter it again.\n')+notice
        form.addRow(window.label(notice,'muted',True))
        ref.addWidget(window.label(self.t('用示例说明你喜欢的结构；只借鉴格式，不照搬示例剧情。','Provide a format example. Its structure is used, not its story.'),'muted',True))
        self.template=QTextEdit();self.template.setAcceptRichText(False);self.template.setPlainText(config['template']);ref.addWidget(self.template,1)
        row=QHBoxLayout();row.addWidget(window.button(self.t('导入文本','Import text'),self.import_text));row.addWidget(window.button(self.t('恢复通用格式','Use default format'),self.reset_format));row.addStretch();ref.addLayout(row)
        self.error_label=window.label('','muted',True);v.addWidget(self.error_label)
        buttons=QHBoxLayout();buttons.addStretch();buttons.addWidget(window.button(self.t('取消','Cancel'),self.reject));buttons.addWidget(window.button(self.t('保存设置','Save settings'),self.save,'primary'));v.addLayout(buttons)
    def update_hint(self):
        kind=self.kind.currentData();self.limit.setEnabled(kind!='chat')
        hints={
            'chat':('支持基础地址（通常以 /v1 结尾）或完整 /chat/completions 地址。本地免密接口可留空 KEY；输出上限由兼容服务商决定。','Use a base URL (usually ending in /v1) or a full /chat/completions URL. Key may be blank for a local API. Output limit is provider-managed.'),
            'responses':('支持基础地址或完整 /responses 地址。','Use a base URL or a full /responses URL.'),
            'anthropic':('使用原生 Messages 接口，例如 https://api.anthropic.com/v1。','Use the native Messages API, e.g. https://api.anthropic.com/v1.'),
            'gemini':('使用原生 generateContent 接口，例如 https://generativelanguage.googleapis.com/v1beta。','Use the native generateContent API, e.g. https://generativelanguage.googleapis.com/v1beta.'),
            'bedrock':('使用区域 runtime 地址和 Bedrock API Key（Bearer），不支持填 AWS Access Key / Secret Key。例如 https://bedrock-runtime.us-east-1.amazonaws.com。','Use a regional runtime URL and a Bedrock bearer API key, not AWS Access Key / Secret Key. Example: https://bedrock-runtime.us-east-1.amazonaws.com.')}
        self.hint.setText(self.t(*hints[kind]))
    def import_text(self):
        path,_=QFileDialog.getOpenFileName(self,self.t('导入参考格式','Import reference format'),'','Text (*.txt *.md)')
        if not path:return
        try:
            raw=Path(path).read_bytes()
            if len(raw)>250000:raise ValueError(self.t('文件过大，请控制在 5 万字符以内。','File too large. Use at most 50,000 characters.'))
            if raw.startswith((b'\xff\xfe',b'\xfe\xff')):text=raw.decode('utf-16')
            else:
                try:text=raw.decode('utf-8-sig')
                except UnicodeDecodeError:text=raw.decode('gb18030')
            if len(text)>50000:raise ValueError(self.t('参考文本最多 5 万字符。','Reference format limit: 50,000 characters.'))
            self.template.setPlainText(text);self.error_label.clear()
        except (OSError,ValueError) as exc:self.error_label.setText(str(exc))
    def reset_format(self):
        if self.window.confirm(self.t('用通用格式替换当前参考文本？','Replace this reference text with the default format?')):self.template.setPlainText(P.defaults()['template'])
    def save(self):
        c=dict(kind=self.kind.currentData(),url=self.url.text().strip(),model=self.model.text().strip(),api_key=self.key.text().strip(),max_tokens=self.limit.value(),template=self.template.toPlainText())
        try:P.save_config(self.window.data,c)
        except Exception as exc:self.error_label.setText(str(exc));return
        self.result_config=c;self.accept()

class EnhancementReview(QDialog):
    def __init__(self,window,draft,result):
        super().__init__(window);self.result_text=None;self.setWindowTitle(window.t('查看增强结果','Review enhanced prompt'));self.resize(min(1040,window.width()-40),min(640,window.height()-60));v=QVBoxLayout(self)
        v.addWidget(window.label(window.t('确认角色编号、剧情和对白；右侧可直接修改后再应用。','Check reference numbering, story and dialogue. Edit the result before applying.'),'muted',True))
        row=QHBoxLayout();left=QVBoxLayout();right=QVBoxLayout();left.addWidget(window.label(window.t('原剧情','Original story'),'section'));right.addWidget(window.label(window.t('增强结果','Enhanced prompt'),'section'));original=QTextEdit();original.setAcceptRichText(False);original.setReadOnly(True);original.setPlainText(draft);left.addWidget(original);self.output=QTextEdit();self.output.setAcceptRichText(False);self.output.setPlainText(result);right.addWidget(self.output);row.addLayout(left,2);row.addLayout(right,3);v.addLayout(row,1)
        buttons=QHBoxLayout();buttons.addWidget(window.button(window.t('复制结果','Copy result'),lambda:QApplication.clipboard().setText(self.output.toPlainText())));buttons.addStretch();buttons.addWidget(window.button(window.t('保留原文','Keep original'),self.reject));buttons.addWidget(window.button(window.t('应用增强结果','Apply enhanced prompt'),self.apply,'primary'));v.addLayout(buttons)
    def apply(self):
        if self.output.toPlainText().strip():self.result_text=self.output.toPlainText().strip();self.accept()
