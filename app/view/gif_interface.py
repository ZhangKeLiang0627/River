# coding:utf-8
import os
import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QFileDialog,
                               QButtonGroup)

from qfluentwidgets import (ScrollArea, FluentIcon, PrimaryPushButton, ComboBox,
                            PushButton, FlowLayout, ToolButton, CaptionLabel,
                            BodyLabel, InfoBar, InfoBarPosition,
                            RadioButton, Slider, ProgressBar, IconWidget, LineEdit, SpinBox)
from ..common.style_sheet import StyleSheet
from ..service.gif_service import (
    get_gif_info, GifCompressWorker, GifExtractWorker,
    save_gif_result, save_gif_results_all, save_gif_results_zip,
)
from ..service.convert_service import format_size


# ============================================================
# 拖拽导入区（仅接受 GIF）
class GifDropZone(QWidget):
    """支持拖拽和点击选择的 GIF 导入区域"""
    filesSelected = Signal(list)  # list of file paths

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

        self.hintLabel = QLabel(self.tr('拖拽 GIF 到此处，或点击选择文件'), self)
        self.hintLabel.setObjectName('hintLabel')
        self.hintLabel.setAlignment(Qt.AlignCenter)

        self.subHintLabel = CaptionLabel(
            self.tr('支持 .gif 格式'), self)
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
            if Path(path).suffix.lower() == '.gif':
                files.append(path)
        if files:
            self.filesSelected.emit(files)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr('选择 GIF'),
            '',
            self.tr('GIF 文件 (*.gif)'))
        if files:
            self.filesSelected.emit(files)


# ============================================================
# 导入 GIF 卡片
class GifCard(QFrame):
    """导入的 GIF 预览卡片"""
    removeClicked = Signal(str)  # file_path

    def __init__(self, file_path: str, info: dict, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setFixedSize(180, 210)
        self.setObjectName('imageCard')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        # 缩略图
        img = Image.open(file_path)
        img.thumbnail((164, 120))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        thumbLabel = QLabel(self)
        thumbLabel.setPixmap(pixmap)
        thumbLabel.setAlignment(Qt.AlignCenter)
        thumbLabel.setFixedHeight(120)
        thumbLabel.setObjectName('thumbLabel')

        # 文件名
        name = Path(file_path).name
        if len(name) > 18:
            name = name[:16] + '…'
        nameLabel = BodyLabel(name, self)

        # 信息标签：帧数 + 尺寸
        info_text = f"{info.get('frame_count', '?')}帧  {info.get('width', '?')}×{info.get('height', '?')}"
        infoLabel = CaptionLabel(info_text, self)

        # 文件大小
        sizeLabel = CaptionLabel(format_size(info.get('file_size', 0)), self)

        # 删除按钮
        btnRemove = ToolButton(FluentIcon.DELETE, self)
        btnRemove.setFixedSize(24, 24)
        btnRemove.clicked.connect(lambda: self.removeClicked.emit(self.file_path))

        layout.addWidget(thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(infoLabel)
        layout.addWidget(sizeLabel)
        btnRemove.move(180 - 28, 4)

        img.close()


# ============================================================
# 结果卡片（压缩）
class CompressResultCard(QFrame):
    """GIF 压缩结果卡片"""
    saveClicked = Signal(dict)

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self.setFixedSize(220, 290)
        self.setObjectName('resultCard')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # 缩略图
        thumb = result['pixmap'].scaled(200, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumbLabel = QLabel(self)
        thumbLabel.setPixmap(thumb)
        thumbLabel.setAlignment(Qt.AlignCenter)
        thumbLabel.setFixedHeight(140)
        thumbLabel.setObjectName('resultThumb')

        # 文件名
        name = result['file_name']
        if len(name) > 20:
            name = name[:18] + '…'
        nameLabel = BodyLabel(name, self)

        # 大小对比
        sizeLabel = CaptionLabel(
            f"{format_size(result['original_size'])} → {format_size(result['compressed_size'])}", self)

        # 压缩率
        ratio = result.get('compress_ratio', 1) * 100
        ratioLabel = CaptionLabel(
            self.tr('压缩率: {:.0f}%').format(100 - ratio), self)

        # 帧数 / 尺寸
        metaLabel = CaptionLabel(
            f"{result['frame_count']}帧  {result['width']}×{result['height']}", self)

        # 保存按钮
        btnSave = PushButton(self.tr('保存'), self, icon=FluentIcon.SAVE)
        btnSave.clicked.connect(lambda: self.saveClicked.emit(self.result))

        layout.addWidget(thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(sizeLabel)
        layout.addWidget(ratioLabel)
        layout.addWidget(metaLabel)
        layout.addStretch()
        layout.addWidget(btnSave)


# ============================================================
# 结果卡片（帧提取）
class ExtractResultCard(QFrame):
    """帧提取结果卡片"""
    saveClicked = Signal(dict)

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self.setFixedSize(200, 260)
        self.setObjectName('resultCard')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # 缩略图
        thumb = result['pixmap'].scaled(180, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumbLabel = QLabel(self)
        thumbLabel.setPixmap(thumb)
        thumbLabel.setAlignment(Qt.AlignCenter)
        thumbLabel.setFixedHeight(130)
        thumbLabel.setObjectName('resultThumb')

        # 文件名
        name = result['file_name']
        if len(name) > 20:
            name = name[:18] + '…'
        nameLabel = BodyLabel(name, self)

        # 帧索引
        indexLabel = CaptionLabel(
            self.tr('第 {} 帧').format(result['index'] + 1), self)

        # 尺寸
        dimLabel = CaptionLabel(
            f"{result['width']} × {result['height']}", self)

        # 保存按钮
        btnSave = PushButton(self.tr('保存'), self, icon=FluentIcon.SAVE)
        btnSave.clicked.connect(lambda: self.saveClicked.emit(self.result))

        layout.addWidget(thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(indexLabel)
        layout.addWidget(dimLabel)
        layout.addStretch()
        layout.addWidget(btnSave)


# ============================================================
# 主页面
class GifInterface(ScrollArea):
    """GIF 工具 — 压缩 & 提取帧"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        # 状态
        self.imported_files = []       # list of file paths
        self.import_cards = {}         # file_path -> GifCard
        self.results = []              # list of result dicts
        self.result_widgets = []       # list of result card widgets
        self._worker = None            # current worker

        self.__initWidget()
        self.__setupSections()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('gifInterface')
        StyleSheet.GIF_INTERFACE.apply(self)

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
        section, layout = self._makeSection(self.tr('导入 GIF'))

        self.dropZone = GifDropZone(self.view)
        self.dropZone.filesSelected.connect(self._onFilesSelected)
        layout.addWidget(self.dropZone)

        # 操作按钮行
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
            self.tr('已导入 0 个 GIF'), self.view)
        btnLayout.addWidget(self.importCountLabel)

        layout.addLayout(btnLayout)

        # 卡片流布局
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
                info = get_gif_info(fp)
                card = GifCard(fp, info, self.importCardsWidget)
                card.removeClicked.connect(self._onRemoveImported)
                self.import_cards[fp] = card
                self.importFlowLayout.addWidget(card)
                added += 1
        if added > 0:
            self.importCardsWidget.setVisible(True)
            self.btnClearAll.setEnabled(True)
            self.importCountLabel.setText(
                self.tr('已导入 {} 个 GIF').format(len(self.imported_files)))

    def _onSelectFiles(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr('选择 GIF'),
            '',
            self.tr('GIF 文件 (*.gif)'))
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
            self.tr('已导入 {} 个 GIF').format(len(self.imported_files)))
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
        self.importCountLabel.setText(self.tr('已导入 0 个 GIF'))

    # ============================================================
    # 2）操作设置区
    # ============================================================
    def __buildSettingsSection(self):
        section, layout = self._makeSection(self.tr('操作设置'))

        # ---- 模式选择 ----
        modeRow = QHBoxLayout()
        modeRow.setSpacing(20)
        self.radioCompress = RadioButton(self.tr('GIF 压缩'), self.view)
        self.radioCompress.setChecked(True)
        self.radioExtract = RadioButton(self.tr('提取帧'), self.view)
        self.modeGroup = QButtonGroup(self.view)
        self.modeGroup.addButton(self.radioCompress, 1)
        self.modeGroup.addButton(self.radioExtract, 2)
        self.modeGroup.buttonClicked.connect(self._onModeChanged)
        modeRow.addWidget(self.radioCompress)
        modeRow.addWidget(self.radioExtract)
        modeRow.addStretch()
        layout.addLayout(modeRow)

        # ---- 压缩设置 ----
        self.compressWidget = QWidget(self.view)
        compressLayout = QVBoxLayout(self.compressWidget)
        compressLayout.setContentsMargins(0, 0, 0, 0)
        compressLayout.setSpacing(8)

        # 颜色数
        colorRow = QHBoxLayout()
        colorRow.setSpacing(8)
        colorRow.addWidget(BodyLabel(self.tr('颜色数:'), self.compressWidget))
        self.colorSlider = Slider(Qt.Horizontal, self.compressWidget)
        self.colorSlider.setRange(2, 256)
        self.colorSlider.setValue(128)
        self.colorSlider.setFixedWidth(200)
        self.colorSlider.valueChanged.connect(
            lambda v: self.colorValueLabel.setText(str(v)))
        self.colorValueLabel = BodyLabel('128', self.compressWidget)
        colorRow.addWidget(self.colorSlider)
        colorRow.addWidget(self.colorValueLabel)
        colorRow.addStretch()
        compressLayout.addLayout(colorRow)

        # 尺寸限制
        resizeRow = QHBoxLayout()
        resizeRow.setSpacing(8)
        resizeRow.addWidget(BodyLabel(self.tr('最大宽度:'), self.compressWidget))
        self.spinMaxWidth = SpinBox(self.compressWidget)
        self.spinMaxWidth.setRange(0, 10000)
        self.spinMaxWidth.setValue(0)
        self.spinMaxWidth.setSuffix(' px')
        self.spinMaxWidth.setSpecialValueText(self.tr('不限'))
        self.spinMaxWidth.setFixedWidth(120)
        resizeRow.addWidget(self.spinMaxWidth)
        resizeRow.addSpacing(16)
        resizeRow.addWidget(BodyLabel(self.tr('最大高度:'), self.compressWidget))
        self.spinMaxHeight = SpinBox(self.compressWidget)
        self.spinMaxHeight.setRange(0, 10000)
        self.spinMaxHeight.setValue(0)
        self.spinMaxHeight.setSuffix(' px')
        self.spinMaxHeight.setSpecialValueText(self.tr('不限'))
        self.spinMaxHeight.setFixedWidth(120)
        resizeRow.addWidget(self.spinMaxHeight)
        resizeRow.addStretch()
        compressLayout.addLayout(resizeRow)
        layout.addWidget(self.compressWidget)

        # ---- 提取设置 ----
        self.extractWidget = QWidget(self.view)
        extractLayout = QVBoxLayout(self.extractWidget)
        extractLayout.setContentsMargins(0, 0, 0, 0)
        extractLayout.setSpacing(8)

        # 输出格式
        fmtRow = QHBoxLayout()
        fmtRow.setSpacing(8)
        fmtRow.addWidget(BodyLabel(self.tr('输出格式:'), self.extractWidget))
        self.cboFrameFormat = ComboBox(self.extractWidget)
        self.cboFrameFormat.addItems(['PNG', 'JPEG'])
        self.cboFrameFormat.setCurrentText('PNG')
        self.cboFrameFormat.setMinimumWidth(120)
        fmtRow.addWidget(self.cboFrameFormat)
        fmtRow.addStretch()
        extractLayout.addLayout(fmtRow)

        # 帧间隔
        intervalRow = QHBoxLayout()
        intervalRow.setSpacing(8)
        intervalRow.addWidget(BodyLabel(
            self.tr('帧间隔:'), self.extractWidget))
        self.spinFrameInterval = SpinBox(self.extractWidget)
        self.spinFrameInterval.setRange(1, 100)
        self.spinFrameInterval.setValue(1)
        self.spinFrameInterval.setSuffix(self.tr(' 帧'))
        self.spinFrameInterval.setFixedWidth(120)
        intervalRow.addWidget(self.spinFrameInterval)
        intervalRow.addWidget(CaptionLabel(
            self.tr('(每隔 N 帧提取一帧)'), self.extractWidget))
        intervalRow.addStretch()
        extractLayout.addLayout(intervalRow)
        self.extractWidget.setVisible(False)
        layout.addWidget(self.extractWidget)

        # ---- 进度条 / 按钮 ----
        self.progressBar = ProgressBar(self.view)
        self.progressBar.setFixedHeight(6)
        self.progressBar.setVisible(False)
        layout.addWidget(self.progressBar)

        self.btnAction = PrimaryPushButton(
            self.tr('开始压缩'), self.view, icon=FluentIcon.PLAY)
        self.btnAction.setFixedWidth(200)
        self.btnAction.clicked.connect(self._onStartAction)
        layout.addWidget(self.btnAction, alignment=Qt.AlignLeft)

        self.vBoxLayout.addWidget(section)

    def _onModeChanged(self):
        mode = self.modeGroup.checkedId()
        self.compressWidget.setVisible(mode == 1)
        self.extractWidget.setVisible(mode == 2)
        self.btnAction.setText(
            self.tr('开始压缩') if mode == 1 else self.tr('提取帧'))

    # ============================================================
    # 3）执行操作
    # ============================================================
    def _onStartAction(self):
        if not self.imported_files:
            InfoBar.warning(
                title=self.tr('提示'),
                content=self.tr('请先导入 GIF 文件'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        self._clearResults()

        mode = self.modeGroup.checkedId()
        self.btnAction.setEnabled(False)
        self.btnAction.setText(self.tr('处理中...'))
        self.progressBar.setVisible(True)

        if mode == 1:
            # GIF 压缩
            colors = self.colorSlider.value()
            max_w = self.spinMaxWidth.value()
            max_h = self.spinMaxHeight.value()
            self._worker = GifCompressWorker(
                list(self.imported_files), colors=colors,
                max_width=max_w, max_height=max_h, parent=self)
        else:
            # 提取帧
            fmt = self.cboFrameFormat.currentText()
            interval = self.spinFrameInterval.value()
            self._worker = GifExtractWorker(
                list(self.imported_files), output_format=fmt,
                frame_interval=interval, parent=self)

        self._worker.progress_update.connect(self._onProgressUpdate)
        self._worker.single_finished.connect(self._onSingleFinished)
        self._worker.all_finished.connect(self._onAllFinished)
        self._worker.start()

    def _onProgressUpdate(self, current: int, total: int):
        self.progressBar.setRange(0, total)
        self.progressBar.setValue(current)

    def _onSingleFinished(self, result: dict):
        self.results.append(result)

        if result['type'] == 'compress':
            card = CompressResultCard(result, self.resultsCardsWidget)
        else:
            card = ExtractResultCard(result, self.resultsCardsWidget)

        card.saveClicked.connect(self._onSaveSingle)
        self.result_widgets.append(card)
        self.resultsFlowLayout.addWidget(card)

        self.resultsSection.setVisible(True)
        self.exportSection.setVisible(True)
        self.btnClearResults.setVisible(True)

    def _onAllFinished(self, results: list):
        self.btnAction.setEnabled(True)
        mode = self.modeGroup.checkedId()
        self.btnAction.setText(
            self.tr('开始压缩') if mode == 1 else self.tr('提取帧'))
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
        self.btnAction.setEnabled(True)
        self._worker = None

    # ============================================================
    # 4）结果展示区
    # ============================================================
    def __buildResultsSection(self):
        self.resultsSection, layout = self._makeSection(self.tr('结果'))
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
        self.prefixEdit.setText('gif_')
        self.prefixEdit.setFixedWidth(200)
        renameRow.addWidget(self.prefixEdit)
        renameRow.addWidget(
            CaptionLabel(self.tr('(如: gif_001.gif)'), self.exportSection))
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
        prefix = self._getPrefix() or 'gif_'
        ext = 'gif' if result.get('type') == 'compress' else 'png'
        base = Path(result.get('file_name', 'output')).stem
        suggested = os.path.join(folder, f"{prefix}{base}.{ext}")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存文件'),
            suggested,
            self.tr('文件 (*.{})').format(ext))
        if save_path:
            save_gif_result(result, save_path)

    def _onSaveAll(self):
        if not self.results:
            return
        folder = self._getOutputDir()
        prefix = self._getPrefix() or 'gif_'
        save_gif_results_all(self.results, folder, prefix)
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
        default_name = os.path.join(folder, 'gif_results.zip')
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存为 ZIP'),
            default_name,
            'ZIP (*.zip)')
        if not save_path:
            return
        prefix = self._getPrefix() or 'gif_'
        save_gif_results_zip(self.results, save_path, prefix)
        InfoBar.success(
            title=self.tr('导出完成'),
            content=self.tr('ZIP 已保存到: {}').format(save_path),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )
