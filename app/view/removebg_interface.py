# coding:utf-8
import os
import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QFileDialog,
                               QApplication)

from qfluentwidgets import (ScrollArea, FluentIcon, PrimaryPushButton,
                            PushButton, FlowLayout, ToolButton, CaptionLabel,
                            BodyLabel, InfoBar, InfoBarPosition,
                            Slider, ProgressBar, IconWidget, LineEdit)
from ..common.style_sheet import StyleSheet
from ..service.removebg_service import (
    RemoveBgWorker,
    save_removebg_result, save_removebg_all, save_removebg_zip,
)
from ..service.convert_service import format_size


# ============================================================
# 拖拽导入区
class RemoveBgDropZone(QWidget):
    """支持拖拽和点击选择的图片导入区域"""
    filesSelected = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(160)
        self.setObjectName('dropZone')
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        self.iconWidget = IconWidget(FluentIcon.ALBUM, self)
        self.iconWidget.setFixedSize(64, 64)

        self.hintLabel = QLabel(self.tr('拖拽图片到此处，或点击选择文件'), self)
        self.hintLabel.setObjectName('hintLabel')
        self.hintLabel.setAlignment(Qt.AlignCenter)

        self.subHintLabel = CaptionLabel(
            self.tr('支持 PNG / JPG / JPEG / BMP / WEBP 格式'), self)
        self.subHintLabel.setObjectName('subHintLabel')
        self.subHintLabel.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.iconWidget, 0, Qt.AlignCenter)
        layout.addWidget(self.hintLabel)
        layout.addWidget(self.subHintLabel)

    def _updateDragState(self, active: bool):
        self.setProperty('dragHover', active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._updateDragState(True)

    def dragLeaveEvent(self, event):  # noqa: ARG002
        self._updateDragState(False)

    def dropEvent(self, event: QDropEvent):
        self._updateDragState(False)
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            ext = Path(path).suffix.lower()
            if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                files.append(path)
        if files:
            self.filesSelected.emit(files)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr('选择图片'),
            '',
            self.tr('图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)'))
        if files:
            self.filesSelected.emit(files)


# ============================================================
# 导入卡片
class ImportCard(QFrame):
    """导入图片预览卡片"""
    removeClicked = Signal(str)

    def __init__(self, file_path: str, pixmap: QPixmap, file_size: int, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setFixedSize(180, 210)
        self.setObjectName('imageCard')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        thumb = pixmap.scaled(164, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumbLabel = QLabel(self)
        thumbLabel.setPixmap(thumb)
        thumbLabel.setAlignment(Qt.AlignCenter)
        thumbLabel.setFixedHeight(120)
        thumbLabel.setObjectName('thumbLabel')

        name = Path(file_path).name
        if len(name) > 18:
            name = name[:16] + '…'
        nameLabel = BodyLabel(name, self)

        sizeLabel = CaptionLabel(format_size(file_size), self)

        btnRemove = ToolButton(FluentIcon.DELETE, self)
        btnRemove.setFixedSize(24, 24)
        btnRemove.clicked.connect(lambda: self.removeClicked.emit(self.file_path))

        layout.addWidget(thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(sizeLabel)
        btnRemove.move(180 - 28, 4)


# ============================================================
# 结果卡片（原图/结果对比）
class RemoveBgResultCard(QFrame):
    """抠图结果卡片 — 原图 vs 结果对比"""
    saveClicked = Signal(dict)

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName('resultCard')

        # 在主线程由 PNG bytes 生成 QPixmap
        orig_pix = QPixmap()
        orig_pix.loadFromData(result['orig_data'])
        res_pix = QPixmap()
        res_pix.loadFromData(result['result_thumb_data'])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 文件名
        name = result['file_name']
        if len(name) > 22:
            name = name[:20] + '…'
        nameLabel = BodyLabel(name, self)
        nameLabel.setAlignment(Qt.AlignCenter)

        # 左右对比布局
        compareLayout = QHBoxLayout()
        compareLayout.setSpacing(8)

        # 原图
        origVBox = QVBoxLayout()
        origVBox.setSpacing(2)
        origCaption = CaptionLabel(self.tr('原图'), self)
        origCaption.setAlignment(Qt.AlignCenter)
        origVBox.addWidget(origCaption)
        origScaled = orig_pix.scaled(140, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        origLabel = QLabel(self)
        origLabel.setPixmap(origScaled)
        origLabel.setAlignment(Qt.AlignCenter)
        origLabel.setFixedSize(140, 100)
        origLabel.setObjectName('resultThumb')
        origVBox.addWidget(origLabel)
        origSize = CaptionLabel(format_size(result['original_size']), self)
        origSize.setAlignment(Qt.AlignCenter)
        origVBox.addWidget(origSize)
        compareLayout.addLayout(origVBox)

        # 箭头
        arrowLabel = CaptionLabel('→', self)
        arrowLabel.setAlignment(Qt.AlignCenter)
        arrowLabel.setFixedWidth(24)
        compareLayout.addWidget(arrowLabel)

        # 结果
        resVBox = QVBoxLayout()
        resVBox.setSpacing(2)
        resCaption = CaptionLabel(self.tr('结果'), self)
        resCaption.setAlignment(Qt.AlignCenter)
        resVBox.addWidget(resCaption)
        resScaled = res_pix.scaled(140, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        resLabel = QLabel(self)
        resLabel.setPixmap(resScaled)
        resLabel.setAlignment(Qt.AlignCenter)
        resLabel.setFixedSize(140, 100)
        resLabel.setObjectName('resultThumb')
        resVBox.addWidget(resLabel)
        res_size = len(result.get('data', b''))
        resSize = CaptionLabel(format_size(res_size), self)
        resSize.setAlignment(Qt.AlignCenter)
        resVBox.addWidget(resSize)
        compareLayout.addLayout(resVBox)

        layout.addLayout(compareLayout)
        layout.addWidget(nameLabel)

        btnSave = PushButton(self.tr('保存'), self, icon=FluentIcon.SAVE)
        btnSave.clicked.connect(lambda: self.saveClicked.emit(self.result))
        layout.addWidget(btnSave)

        self.setFixedWidth(380)


# ============================================================
# 主页面
class RemoveBgInterface(ScrollArea):
    """抠图 — 自动去除图片背景"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        # 状态
        self.imported_files = []       # list of file paths
        self.import_cards = {}         # file_path -> ImportCard
        self.results = []              # list of result dicts
        self.result_widgets = []       # list of RemoveBgResultCard
        self._worker = None

        self.__initWidget()
        self.__setupSections()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('removebgInterface')
        StyleSheet.REMOVEBG_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def __setupSections(self):
        self.__buildImportSection()
        self.__buildSettingsSection()
        self.__buildResultsSection()
        self.__buildExportSection()

    # -------- 工具：创建区段标题 --------
    def _makeSection(self, title: str):
        w = QWidget(self.view)
        w.setObjectName('sectionWidget')
        layout = QVBoxLayout(w)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.setSpacing(12)
        titleLabel = QLabel(title, w)
        titleLabel.setObjectName('viewTitleLabel')
        layout.addWidget(titleLabel)
        return w, layout

    # ============================================================
    # 1）导入区
    # ============================================================
    def __buildImportSection(self):
        section, layout = self._makeSection(self.tr('导入图片'))

        self.dropZone = RemoveBgDropZone(self.view)
        self.dropZone.filesSelected.connect(self._onFilesSelected)
        layout.addWidget(self.dropZone)

        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(8)

        self.btnSelectFiles = PushButton(
            self.tr('选择文件'), self, icon=FluentIcon.ADD)
        self.btnSelectFiles.clicked.connect(self._onSelectFiles)
        btnLayout.addWidget(self.btnSelectFiles)

        self.btnClearAll = PushButton(
            self.tr('清空列表'), self, icon=FluentIcon.CLOSE)
        self.btnClearAll.clicked.connect(self._onClearImport)
        self.btnClearAll.setEnabled(False)
        btnLayout.addWidget(self.btnClearAll)

        btnLayout.addStretch()

        self.importCountLabel = CaptionLabel(
            self.tr('已导入 0 张图片'), self.view)
        btnLayout.addWidget(self.importCountLabel)

        layout.addLayout(btnLayout)

        self.importFlowLayout = FlowLayout()
        self.importFlowLayout.setContentsMargins(0, 0, 0, 0)
        self.importFlowLayout.setHorizontalSpacing(12)
        self.importFlowLayout.setVerticalSpacing(12)

        self.importCardsWidget = QWidget(self.view)
        self.importCardsWidget.setLayout(self.importFlowLayout)
        self.importCardsWidget.setVisible(False)
        layout.addWidget(self.importCardsWidget)

        self.vBoxLayout.addWidget(section)

    def _onFilesSelected(self, files: list):
        added = 0
        for fp in files:
            if fp not in self.imported_files:
                self.imported_files.append(fp)
                try:
                    img = Image.open(fp)
                    img.thumbnail((200, 200))
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.getvalue())
                except Exception:
                    pixmap = QPixmap(100, 100)
                    pixmap.fill(QColor(200, 200, 200))

                card = ImportCard(fp, pixmap, os.path.getsize(fp),
                                 self.importCardsWidget)
                card.removeClicked.connect(self._onRemoveImported)
                self.import_cards[fp] = card
                self.importFlowLayout.addWidget(card)
                added += 1

        if added > 0:
            self.importCardsWidget.setVisible(True)
            self.btnClearAll.setEnabled(True)
            self.importCountLabel.setText(
                self.tr('已导入 {} 张图片').format(len(self.imported_files)))

    def _onSelectFiles(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr('选择图片'),
            '',
            self.tr('图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)'))
        if files:
            self._onFilesSelected(files)

    def _onRemoveImported(self, file_path: str):
        if file_path in self.imported_files:
            self.imported_files.remove(file_path)
        card = self.import_cards.pop(file_path, None)
        if card:
            self.importFlowLayout.removeWidget(card)
            card.deleteLater()
        self.importCountLabel.setText(
            self.tr('已导入 {} 张图片').format(len(self.imported_files)))
        if not self.imported_files:
            self.importCardsWidget.setVisible(False)
            self.btnClearAll.setEnabled(False)

    def _onClearImport(self):
        for fp in list(self.imported_files):
            card = self.import_cards.pop(fp, None)
            if card:
                self.importFlowLayout.removeWidget(card)
                card.deleteLater()
        self.imported_files.clear()
        self.importCardsWidget.setVisible(False)
        self.btnClearAll.setEnabled(False)
        self.importCountLabel.setText(self.tr('已导入 0 张图片'))

    # ============================================================
    # 2）参数设置区
    # ============================================================
    def __buildSettingsSection(self):
        section, layout = self._makeSection(self.tr('抠图设置'))

        # 容差说明
        descLabel = CaptionLabel(
            self.tr('容差越大，去除背景的范围越广；容差过小可能导致边缘残留。'), self.view)
        layout.addWidget(descLabel)

        # 容差滑块
        toleranceRow = QHBoxLayout()
        toleranceRow.setSpacing(8)
        toleranceRow.addWidget(BodyLabel(self.tr('容差:'), self.view))
        self.toleranceSlider = Slider(Qt.Horizontal, self.view)
        self.toleranceSlider.setRange(5, 150)
        self.toleranceSlider.setValue(40)
        self.toleranceSlider.setFixedWidth(250)
        self.toleranceSlider.valueChanged.connect(
            lambda v: self.toleranceValueLabel.setText(str(v)))
        self.toleranceValueLabel = BodyLabel('40', self.view)
        toleranceRow.addWidget(self.toleranceSlider)
        toleranceRow.addWidget(self.toleranceValueLabel)
        toleranceRow.addStretch()
        layout.addLayout(toleranceRow)

        # 进度条
        self.progressBar = ProgressBar(self.view)
        self.progressBar.setFixedHeight(6)
        self.progressBar.setVisible(False)
        layout.addWidget(self.progressBar)

        # 抠图按钮
        self.btnRemoveBg = PrimaryPushButton(
            self.tr('开始抠图'), self.view, icon=FluentIcon.PLAY)
        self.btnRemoveBg.setFixedWidth(200)
        self.btnRemoveBg.clicked.connect(self._onStartRemove)
        layout.addWidget(self.btnRemoveBg, alignment=Qt.AlignLeft)

        self.vBoxLayout.addWidget(section)

    # ============================================================
    # 3）执行抠图
    # ============================================================
    def _onStartRemove(self):
        if not self.imported_files:
            InfoBar.warning(
                title=self.tr('提示'),
                content=self.tr('请先导入图片'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        self._clearResults()

        tolerance = self.toleranceSlider.value()
        self.btnRemoveBg.setEnabled(False)
        self.btnRemoveBg.setText(self.tr('抠图中...'))
        self.progressBar.setVisible(True)

        self._worker = RemoveBgWorker(
            list(self.imported_files), tolerance=tolerance, parent=self)
        self._worker.progress_update.connect(self._onProgressUpdate)
        self._worker.single_finished.connect(self._onSingleFinished)
        self._worker.all_finished.connect(self._onAllFinished)
        self._worker.start()

    def _onProgressUpdate(self, current: int, total: int):
        self.progressBar.setRange(0, total)
        self.progressBar.setValue(current)
        QApplication.processEvents()

    def _onSingleFinished(self, result: dict):
        self.results.append(result)

        card = RemoveBgResultCard(result, self.resultsCardsWidget)
        card.saveClicked.connect(self._onSaveSingle)
        self.result_widgets.append(card)
        self.resultsFlowLayout.addWidget(card)

        self.resultsSection.setVisible(True)
        self.exportSection.setVisible(True)
        self.btnClearResults.setVisible(True)
        self.resultCountLabel.setText(
            self.tr('共 {} 个结果').format(len(self.results)))
        QApplication.processEvents()

    def _onAllFinished(self, results: list):
        self.btnRemoveBg.setEnabled(True)
        self.btnRemoveBg.setText(self.tr('开始抠图'))
        self.progressBar.setVisible(False)

        count_label = self.tr('共 {} 个结果').format(len(results))
        self.resultCountLabel.setText(count_label)
        self._worker = None

        if results:
            InfoBar.success(
                title=self.tr('完成'),
                content=count_label,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def _clearResults(self):
        self.results.clear()
        for w in self.result_widgets:
            self.resultsFlowLayout.removeWidget(w)
            w.deleteLater()
        self.result_widgets.clear()

    def _onClearResults(self):
        self._clearResults()
        self.resultsSection.setVisible(False)
        self.exportSection.setVisible(False)
        self.btnClearResults.setVisible(False)
        self.btnRemoveBg.setEnabled(True)
        self._worker = None

    # ============================================================
    # 4）结果展示区
    # ============================================================
    def __buildResultsSection(self):
        self.resultsSection, layout = self._makeSection(self.tr('抠图结果'))
        self.resultsSection.setVisible(False)

        resultHeaderLayout = QHBoxLayout()
        resultHeaderLayout.setSpacing(8)
        self.resultCountLabel = CaptionLabel('', self.resultsSection)
        resultHeaderLayout.addWidget(self.resultCountLabel)

        self.btnClearResults = PushButton(
            self.tr('清空结果'), self.resultsSection, icon=FluentIcon.CLOSE)
        self.btnClearResults.clicked.connect(self._onClearResults)
        self.btnClearResults.setVisible(False)
        resultHeaderLayout.addWidget(self.btnClearResults)

        resultHeaderLayout.addStretch()
        layout.addLayout(resultHeaderLayout)

        self.resultsFlowLayout = FlowLayout()
        self.resultsFlowLayout.setContentsMargins(0, 0, 0, 0)
        self.resultsFlowLayout.setHorizontalSpacing(12)
        self.resultsFlowLayout.setVerticalSpacing(12)

        self.resultsCardsWidget = QWidget(self.resultsSection)
        self.resultsCardsWidget.setLayout(self.resultsFlowLayout)

        layout.addWidget(self.resultsCardsWidget)
        self.vBoxLayout.addWidget(self.resultsSection)

    # ============================================================
    # 5）导出区
    # ============================================================
    def __buildExportSection(self):
        self.exportSection, layout = self._makeSection(self.tr('导出'))
        self.exportSection.setVisible(False)

        # 文件名前缀
        renameRow = QHBoxLayout()
        renameRow.setSpacing(8)
        renameRow.addWidget(BodyLabel(self.tr('文件名前缀:'), self.exportSection))
        self.prefixEdit = LineEdit(self.exportSection)
        self.prefixEdit.setText('removed_bg_')
        self.prefixEdit.setFixedWidth(200)
        renameRow.addWidget(self.prefixEdit)
        renameRow.addWidget(
            CaptionLabel(self.tr('(如: removed_bg_001.png)'), self.exportSection))
        renameRow.addStretch()
        layout.addLayout(renameRow)

        # 输出目录
        outDirRow = QHBoxLayout()
        outDirRow.setSpacing(8)
        outDirRow.addWidget(
            BodyLabel(self.tr('保存位置:'), self.exportSection))
        self.outputDirLabel = BodyLabel(
            os.path.abspath('.'), self.exportSection)
        self.outputDirLabel.setObjectName('outputDirLabel')
        outDirRow.addWidget(self.outputDirLabel, 1)
        self.btnBrowseDir = PushButton(
            self.tr('浏览...'), self.exportSection, icon=FluentIcon.FOLDER)
        self.btnBrowseDir.clicked.connect(self._onBrowseOutputDir)
        outDirRow.addWidget(self.btnBrowseDir)
        layout.addLayout(outDirRow)

        # 操作按钮
        btnRow = QHBoxLayout()
        btnRow.setSpacing(12)
        self.btnSaveAll = PushButton(
            self.tr('全部保存'), self.exportSection, icon=FluentIcon.SAVE)
        self.btnSaveAll.clicked.connect(self._onSaveAll)
        self.btnSaveAll.setFixedWidth(140)
        btnRow.addWidget(self.btnSaveAll)
        self.btnSaveZip = PushButton(
            self.tr('保存为 ZIP'), self.exportSection, icon=FluentIcon.DOWNLOAD)
        self.btnSaveZip.clicked.connect(self._onSaveZip)
        self.btnSaveZip.setFixedWidth(140)
        btnRow.addWidget(self.btnSaveZip)
        btnRow.addStretch()
        layout.addLayout(btnRow)

        self.vBoxLayout.addWidget(self.exportSection)

    def _onBrowseOutputDir(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.tr('选择保存位置'), self.outputDirLabel.text())
        if folder:
            self.outputDirLabel.setText(folder)

    def _getOutputDir(self) -> str:
        return self.outputDirLabel.text()

    def _getPrefix(self) -> str:
        return self.prefixEdit.text().strip()

    # -------- 导出 --------
    def _onSaveSingle(self, result: dict):
        folder = self._getOutputDir()
        prefix = self._getPrefix() or 'removed_bg_'
        base = Path(result.get('file_name', 'output')).stem
        suggested = os.path.join(folder, f"{prefix}{base}.png")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存 PNG'),
            suggested,
            'PNG (*.png)')
        if save_path:
            save_removebg_result(result, save_path)

    def _onSaveAll(self):
        if not self.results:
            return
        folder = self._getOutputDir()
        prefix = self._getPrefix() or 'removed_bg_'
        save_removebg_all(self.results, folder, prefix)
        InfoBar.success(
            title=self.tr('导出完成'),
            content=self.tr('已保存 {} 个文件到: {}').format(
                len(self.results), folder),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def _onSaveZip(self):
        if not self.results:
            return
        folder = self._getOutputDir()
        default_name = os.path.join(folder, 'removebg_results.zip')
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存为 ZIP'),
            default_name,
            'ZIP (*.zip)')
        if not save_path:
            return
        prefix = self._getPrefix() or 'removed_bg_'
        save_removebg_zip(self.results, save_path, prefix)
        InfoBar.success(
            title=self.tr('导出完成'),
            content=self.tr('ZIP 已保存到: {}').format(save_path),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )
