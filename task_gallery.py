"""Scrollable task cards with bounded, cached background thumbnail extraction."""
import hashlib,os,subprocess,threading
from pathlib import Path
from PyQt6.QtCore import Qt,QSize,pyqtSignal,QRect
from PyQt6.QtGui import QIcon,QPixmap,QPainter,QColor,QPolygon
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QListWidget,QListWidgetItem,QAbstractItemView,QStyledItemDelegate,QStyleOptionViewItem,QStyle
import engine as E

class CardDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        rect=option.rect;icon=index.data(Qt.ItemDataRole.DecorationRole);lines=str(index.data(Qt.ItemDataRole.DisplayRole) or '').split('\n')
        painter.save();painter.setClipRect(rect);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setBrush(QColor('#e1edff' if selected else '#ffffff'));painter.setPen(QColor('#397ee8' if selected else '#d9e5ff'));painter.drawRoundedRect(rect.adjusted(1,1,-2,-2),10,10)
        if icon is not None:painter.drawPixmap(rect.x()+(rect.width()-160)//2,rect.y()+5,icon.pixmap(160,90))
        painter.setFont(option.font);painter.setPen(QColor('#24334c'))
        painter.drawText(QRect(rect.x()+7,rect.y()+97,rect.width()-14,18),Qt.AlignmentFlag.AlignCenter,lines[0][5:] if lines and len(lines[0])==19 else (lines[0] if lines else ''))
        painter.setPen(QColor('#4670aa'));painter.drawText(QRect(rect.x()+7,rect.y()+116,rect.width()-14,18),Qt.AlignmentFlag.AlignCenter,lines[1] if len(lines)>1 else '')
        painter.restore()

class TaskGallery(QListWidget):
    thumbnail_ready=pyqtSignal(str,str)
    def __init__(self,parent=None):
        super().__init__(parent);self.cancel=threading.Event();self.cards={};self.process=None;self.worker=None;self.lock=threading.Lock()
        self.setItemDelegate(CardDelegate(self));self.setViewMode(QListWidget.ViewMode.IconMode);self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static);self.setWrapping(True);self.setSpacing(6)
        self.setIconSize(QSize(160,90));self.setGridSize(QSize(186,142));self.setWordWrap(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(310);self.setMaximumHeight(350)
        self.setStyleSheet('QListWidget::item {border:1px solid #d9e5ff;border-radius:10px;padding:5px;background:#ffffff;} QListWidget::item:selected {background:#e1edff;border:2px solid #397ee8;} QListWidget::item:hover {background:#f0f6ff;}')
        pix=QPixmap(160,90);pix.fill(QColor('#edf3ff'));p=QPainter(pix);p.setBrush(QColor('#a8bfe6'));p.setPen(Qt.PenStyle.NoPen);p.drawPolygon(QPolygon([QPoint(69,29),QPoint(69,61),QPoint(96,45)]));p.end();self.placeholder=QIcon(pix)
        self.thumbnail_ready.connect(self.apply_thumbnail)
        self.destroyed.connect(lambda *_:self.stop_loading())
    def stop_loading(self):
        self.cancel.set()
        with self.lock:
            if self.process is not None and self.process.poll() is None:self.process.kill()
        if self.worker is not None:self.worker.join(timeout=2)
    def reset_cards(self):
        self.stop_loading();self.cancel=threading.Event();self.clear();self.cards={}
    def add_card(self,job,text,tooltip,cache):
        item=QListWidgetItem(self.placeholder,text);item.setData(Qt.ItemDataRole.UserRole,job['id']);item.setSizeHint(QSize(180,136));self.addItem(item)
        video=next((Path(f) for f in reversed(job.get('files',[])) if Path(f).is_file() and Path(f).suffix.lower() in ('.mp4','.mov','.mkv','.webm','.avi')),None)
        if video is None:return item,None
        try:
            stat=video.stat();key=hashlib.sha256(f'{video.resolve()}|{stat.st_size}|{stat.st_mtime_ns}'.encode()).hexdigest()
        except OSError:return item,None
        target=Path(cache)/(key+'.png');self.cards.setdefault(key,[]).append(item)
        if target.is_file():
            icon=QIcon(str(target))
            if not icon.isNull():item.setIcon(icon);return item,None
        return item,(key,video,target)
    def load_thumbnails(self,pending):
        cancel=self.cancel
        def run():
            for key,video,target in pending:
                if cancel.is_set():return
                try:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with self.lock:
                        if cancel.is_set():return
                        self.process=subprocess.Popen([E.ffmpeg_path(),'-hide_banner','-loglevel','error','-i',str(video),'-frames:v','1','-vf','scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2','-y',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000 if os.name=='nt' else 0)
                    try:self.process.communicate(timeout=12)
                    except subprocess.TimeoutExpired:
                        self.process.kill();self.process.communicate();continue
                    if self.process.returncode==0 and not cancel.is_set():self.thumbnail_ready.emit(key,str(target))
                except (OSError,subprocess.TimeoutExpired,RuntimeError):continue
        if pending:self.worker=threading.Thread(target=run,daemon=True);self.worker.start()
    def apply_thumbnail(self,key,path):
        icon=QIcon(path)
        if not icon.isNull():
            for item in self.cards.get(key,[]):item.setIcon(icon)
