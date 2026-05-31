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
                            RadioButton, Slider, LineEdit, ProgressBar, IconWidget)
from ..common.config import cfg
from ..common.style_sheet import StyleSheet
from ..service.convert_service import (
    SUPPORTED_FORMATS, SIZE_LIMITS,
    format_size, _normalize_format, _format_dimensions,
    save_result_to_path, save_all_results, save_results_as_zip,
    ConvertWorker
)


# ============================================================
# 拖拽导入区域
class DropZoneWidget(QWidget):
    """支持拖拽和点击选择的图片导入区域"""
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

        # 使用 qfluentwidgets IconWidget 替代 emoji 文本
        self.iconWidget = IconWidget(FluentIcon.ALBUM, self)
        self.iconWidget.setFixedSize(64, 64)

        self.hintLabel = QLabel(self.tr('拖拽图片到此处，或点击选择文件'), self)
        self.hintLabel.setObjectName('hintLabel')
        self.hintLabel.setAlignment(Qt.AlignCenter)

        self.subHintLabel = CaptionLabel(
            self.tr('支持 PNG / JPG / JPEG / GIF / BMP / WEBP 格式'), self)
        self.subHintLabel.setObjectName('subHintLabel')
        self.subHintLabel.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.iconWidget, 0, Qt.AlignCenter)
        layout.addWidget(self.hintLabel)
        layout.addWidget(self.subHintLabel)

        # 样式由 QSS 统一管理（home_interface.qss）

    # -------- 通过 QSS 属性选择器切换拖拽高亮 --------
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
            if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'):
                files.append(path)
        if files:
            self.filesSelected.emit(files)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr('选择图片'),
            '',
            self.tr('图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)'))
        if files:
            self.filesSelected.emit(files)


# ============================================================
# 导入图片卡片
class ImageCard(QFrame):
    """导入的图片预览卡片"""
    removeClicked = Signal(str)  # file_path

    def __init__(self, file_path: str, pixmap: QPixmap, file_size: int, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setFixedSize(180, 210)
        self.setObjectName('imageCard')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        # 缩略图
        thumb = pixmap.scaled(164, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbLabel = QLabel(self)
        self.thumbLabel.setPixmap(thumb)
        self.thumbLabel.setAlignment(Qt.AlignCenter)
        self.thumbLabel.setFixedHeight(120)
        self.thumbLabel.setObjectName('thumbLabel')

        # 文件名（截断）
        name = Path(file_path).name
        if len(name) > 18:
            name = name[:16] + '…'
        nameLabel = BodyLabel(name, self)

        # 文件大小
        sizeLabel = CaptionLabel(format_size(file_size), self)

        # 删除按钮
        btnRemove = ToolButton(FluentIcon.DELETE, self)
        btnRemove.setFixedSize(24, 24)
        btnRemove.clicked.connect(lambda: self.removeClicked.emit(self.file_path))

        layout.addWidget(self.thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(sizeLabel)

        # 删除按钮放右上角
        btnRemove.move(180 - 28, 4)

        # 样式由 QSS 文件统一管理 —— 详见 home_interface.qss


# ============================================================
# 转换结果卡片
class ResultCard(QFrame):
    """转换后的结果卡片"""
    saveClicked = Signal(dict)  # result dict

    def __init__(self, result: dict, index: int, parent=None):
        super().__init__(parent)
        self.result = result
        self.index = index
        self.setFixedSize(200, 280)
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

        # 原始文件名
        name = result['file_name']
        if len(name) > 20:
            name = name[:18] + '…'
        nameLabel = BodyLabel(name, self)

        # 格式信息
        fmtInfo = CaptionLabel(
            f"{self.tr('原')}: {result['original_format']}  →  {result['target_format']}", self)

        # 大小对比
        sizeInfo = CaptionLabel(
            f"{format_size(result['original_size'])} → {format_size(result['converted_size'])}", self)

        # 尺寸
        dimLabel = CaptionLabel(
            _format_dimensions(result['width'], result['height']), self)

        # 保存按钮
        btnSave = PushButton(self.tr('保存'), self, icon=FluentIcon.SAVE)
        btnSave.clicked.connect(lambda: self.saveClicked.emit(self.result))

        layout.addWidget(thumbLabel)
        layout.addWidget(nameLabel)
        layout.addWidget(fmtInfo)
        layout.addWidget(sizeInfo)
        layout.addWidget(dimLabel)
        layout.addStretch()
        layout.addWidget(btnSave)

        # 样式由 QSS 文件统一管理 —— 详见 home_interface.qss


# ============================================================
# 主页（图片格式转换）
class HomeInterface(ScrollArea):
    """ Home interface — 图片格式转换工具 """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        # 状态
        self.imported_files = []       # list of file paths (deduped)
        self.import_cards = {}         # file_path -> ImageCard
        self.conversion_results = []   # list of result dicts
        self.result_cards = []         # list of ResultCard widgets
        self._worker = None            # ConvertWorker instance

        self.__initWidget()
        self.__setupSections()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('homeInterface')
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def __setupSections(self):
        """构建所有功能区"""
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

        self.dropZone = DropZoneWidget(self.view)
        self.dropZone.filesSelected.connect(self._onFilesSelected)
        layout.addWidget(self.dropZone)

        # 操作按钮行
        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(8)

        self.btnSelectFiles = PushButton(
            self.tr('选择文件'), self, icon=FluentIcon.ADD)
        self.btnSelectFiles.clicked.connect(self._onSelectFiles)
        btnLayout.addWidget(self.btnSelectFiles)

        self.btnSelectFolder = PushButton(
            self.tr('选择文件夹'), self, icon=FluentIcon.FOLDER)
        self.btnSelectFolder.clicked.connect(self._onSelectFolder)
        btnLayout.addWidget(self.btnSelectFolder)

        self.btnClearAll = PushButton(
            self.tr('清空列表'), self, icon=FluentIcon.CLOSE)
        self.btnClearAll.clicked.connect(self._onClearAll)
        self.btnClearAll.setEnabled(False)
        btnLayout.addWidget(self.btnClearAll)

        btnLayout.addStretch()

        # 已导入数量
        self.importCountLabel = CaptionLabel(
            self.tr('已导入 0 张图片'), self.view)
        btnLayout.addWidget(self.importCountLabel)

        layout.addLayout(btnLayout)

        # 图片卡片流布局（_makeSection 已带 36px 水平边距，内部不再重复）
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
        """接收新选择的文件，去重后添加"""
        added = 0
        for fp in files:
            if fp not in self.imported_files:
                self.imported_files.append(fp)
                # 生成缩略图
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

                card = ImageCard(fp, pixmap, os.path.getsize(fp),
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
            self.tr('图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)'))
        if files:
            self._onFilesSelected(files)

    def _onSelectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr('选择文件夹'))
        if not folder:
            return
        exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        files = []
        for f in Path(folder).iterdir():
            if f.is_file() and f.suffix.lower() in exts:
                files.append(str(f))
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

    def _onClearAll(self):
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
    # 2）转换设置区
    # ============================================================
    def __buildSettingsSection(self):
        section, layout = self._makeSection(self.tr('转换设置'))

        # 目标格式
        fmtRow = QHBoxLayout()
        fmtRow.setSpacing(8)
        fmtRow.addWidget(BodyLabel(self.tr('目标格式:'), self.view))
        self.cboFormat = ComboBox(self.view)
        self.cboFormat.addItems(SUPPORTED_FORMATS)
        self.cboFormat.setCurrentText('PNG')
        self.cboFormat.setMinimumWidth(160)
        self.cboFormat.currentTextChanged.connect(self._onFormatChanged)
        fmtRow.addWidget(self.cboFormat)
        fmtRow.addStretch()
        layout.addLayout(fmtRow)

        # 品质设置
        self.qualityWidget = QWidget(self.view)
        qualityLayout = QVBoxLayout(self.qualityWidget)
        qualityLayout.setContentsMargins(0, 0, 0, 0)

        # 品质单选组（使用 qfluentwidgets RadioButton）
        radioRow = QHBoxLayout()
        radioRow.setSpacing(20)

        self.radioQuality = RadioButton(self.tr('按品质(%)'), self.qualityWidget)
        self.radioQuality.setChecked(True)
        self.radioSizeLimit = RadioButton(
            self.tr('限制文件大小'), self.qualityWidget)
        self.qualityModeGroup = QButtonGroup(self.qualityWidget)
        self.qualityModeGroup.addButton(self.radioQuality, 1)
        self.qualityModeGroup.addButton(self.radioSizeLimit, 2)
        self.qualityModeGroup.buttonClicked.connect(
            self._onQualityModeChanged)

        radioRow.addWidget(self.radioQuality)
        radioRow.addWidget(self.radioSizeLimit)
        radioRow.addStretch()
        qualityLayout.addLayout(radioRow)

        # 品质滑块行（使用 qfluentwidgets Slider）
        sliderRow = QHBoxLayout()
        sliderRow.setSpacing(8)

        self.qualitySlider = Slider(Qt.Horizontal, self.qualityWidget)
        self.qualitySlider.setRange(1, 100)
        self.qualitySlider.setValue(85)
        self.qualitySlider.valueChanged.connect(self._onQualitySliderChanged)
        self.qualityValueLabel = BodyLabel('85%', self.qualityWidget)

        sliderRow.addWidget(self.qualitySlider)
        sliderRow.addWidget(self.qualityValueLabel)
        qualityLayout.addLayout(sliderRow)

        # 大小限制下拉
        self.sizeLimitWidget = QWidget(self.qualityWidget)
        sizeLimitRow = QHBoxLayout(self.sizeLimitWidget)
        sizeLimitRow.setSpacing(8)
        self.cboSizeLimit = ComboBox(self.qualityWidget)
        self.cboSizeLimit.addItems([label for label, _ in SIZE_LIMITS])
        self.cboSizeLimit.setCurrentIndex(0)
        self.cboSizeLimit.setMinimumWidth(160)
        sizeLimitRow.addWidget(CaptionLabel(
            self.tr('上限:'), self.qualityWidget))
        sizeLimitRow.addWidget(self.cboSizeLimit)
        sizeLimitRow.addStretch()
        self.sizeLimitWidget.setVisible(False)
        qualityLayout.addWidget(self.sizeLimitWidget)

        layout.addWidget(self.qualityWidget)

        # 进度条（使用 qfluentwidgets ProgressBar）
        self.progressBar = ProgressBar(self.view)
        self.progressBar.setVisible(False)
        self.progressBar.setFixedHeight(6)
        layout.addWidget(self.progressBar)

        # 转换按钮
        self.btnConvert = PrimaryPushButton(
            self.tr('开始转换'), self.view, icon=FluentIcon.PLAY)
        self.btnConvert.setFixedWidth(200)
        self.btnConvert.clicked.connect(self._onStartConversion)
        layout.addWidget(self.btnConvert, alignment=Qt.AlignLeft)

        self.vBoxLayout.addWidget(section)

        # 初始隐藏品质设置（默认格式 PNG 不支持品质控制）
        self._onFormatChanged('PNG')

    def _onFormatChanged(self, fmt: str):
        norm = _normalize_format(fmt)
        can_control = norm in ('JPEG', 'WEBP')
        self.qualityWidget.setVisible(can_control)
        if not can_control:
            self.radioQuality.setChecked(True)

    def _onQualityModeChanged(self):
        mode = self.qualityModeGroup.checkedId()
        self.qualitySlider.setVisible(mode == 1)
        self.qualityValueLabel.setVisible(mode == 1)
        self.sizeLimitWidget.setVisible(mode == 2)

    def _onQualitySliderChanged(self, val: int):
        self.qualityValueLabel.setText(f'{val}%')

    def _getSizeLimitBytes(self) -> int:
        idx = self.cboSizeLimit.currentIndex()
        if 0 <= idx < len(SIZE_LIMITS):
            return SIZE_LIMITS[idx][1]
        return 0

    def _getQuality(self) -> int:
        return self.qualitySlider.value()

    # ============================================================
    # 3）执行转换
    # ============================================================
    def _onStartConversion(self):
        if not self.imported_files:
            return

        target = self.cboFormat.currentText()
        size_limit = 0 if self.radioQuality.isChecked() else self._getSizeLimitBytes()
        quality = self._getQuality()

        # 清理旧结果
        self._clearResults()

        # 禁用按钮、显示进度
        self.btnConvert.setEnabled(False)
        self.btnConvert.setText(self.tr('转换中...'))
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, len(self.imported_files))
        self.progressBar.setValue(0)

        # 启动工作线程
        self._worker = ConvertWorker(
            list(self.imported_files), target, quality, size_limit, self)
        self._worker.progress_update.connect(self._onProgressUpdate)
        self._worker.single_finished.connect(self._onSingleFinished)
        self._worker.all_finished.connect(self._onAllFinished)
        self._worker.start()

    def _onProgressUpdate(self, current: int, total: int):  # noqa: ARG002
        self.progressBar.setValue(current)

    def _onSingleFinished(self, result: dict):
        self.conversion_results.append(result)
        idx = len(self.conversion_results) - 1

        card = ResultCard(result, idx, self.resultsCardsWidget)
        card.saveClicked.connect(self._onSaveSingle)
        self.result_cards.append(card)
        self.resultsFlowLayout.addWidget(card)

        self.resultsSection.setVisible(True)
        self.exportSection.setVisible(True)
        self.btnClearResults.setVisible(True)

    def _onAllFinished(self, results: list):
        self.btnConvert.setEnabled(True)
        self.btnConvert.setText(self.tr('开始转换'))
        self.progressBar.setVisible(False)

        self.resultCountLabel.setText(
            self.tr('共转换 {} 张图片').format(len(results)))
        self._worker = None

        if results:
            InfoBar.success(
                title=self.tr('转换完成'),
                content=self.tr('共成功转换 {} 张图片').format(len(results)),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def _clearResults(self):
        self.conversion_results.clear()
        for card in self.result_cards:
            self.resultsFlowLayout.removeWidget(card)
            card.deleteLater()
        self.result_cards.clear()

    def _onClearResults(self):
        """清空所有转换结果并隐藏相关区段"""
        self._clearResults()
        self.resultsSection.setVisible(False)
        self.exportSection.setVisible(False)
        self.btnClearResults.setVisible(False)
        self.btnConvert.setEnabled(True)
        self.btnConvert.setText(self.tr('开始转换'))
        self.progressBar.setRange(0, 0)
        self.progressBar.setValue(0)
        self._worker = None

    # ============================================================
    # 4）结果展示区
    # ============================================================
    def __buildResultsSection(self):
        self.resultsSection, layout = self._makeSection(self.tr('转换结果'))
        self.resultsSection.setVisible(False)

        # 计数标签 + 清空按钮
        resultHeaderLayout = QHBoxLayout()
        resultHeaderLayout.setSpacing(8)
        self.resultCountLabel = CaptionLabel('', self.resultsSection)
        resultHeaderLayout.addWidget(self.resultCountLabel)

        self.btnClearResults = PushButton(
            self.tr('清空结果'), self.resultsSection, icon=FluentIcon.CLOSE)
        # self.btnClearResults.setFixedWidth(120)
        self.btnClearResults.clicked.connect(self._onClearResults)
        self.btnClearResults.setVisible(False)
        resultHeaderLayout.addWidget(self.btnClearResults)

        resultHeaderLayout.addStretch()
        layout.addLayout(resultHeaderLayout)

        # 流布局位于已带 36px 边距的 section 内，内部不再重复
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

        # 重命名前缀（使用 qfluentwidgets LineEdit）
        renameRow = QHBoxLayout()
        renameRow.setSpacing(8)
        renameRow.addWidget(BodyLabel(self.tr('文件名前缀:'), self.exportSection))
        self.prefixEdit = LineEdit(self.exportSection)
        self.prefixEdit.setText(self.tr('converted_'))
        self.prefixEdit.setFixedWidth(200)
        renameRow.addWidget(self.prefixEdit)
        renameRow.addWidget(
            CaptionLabel(self.tr('(如: converted_001.png)'), self.exportSection))
        renameRow.addStretch()
        layout.addLayout(renameRow)

        # 输出目录
        outDirRow = QHBoxLayout()
        outDirRow.setSpacing(8)
        outDirRow.addWidget(
            BodyLabel(self.tr('保存位置:'), self.exportSection))
        default_dir = os.path.abspath(cfg.get(cfg.downloadFolder))
        self.outputDirLabel = BodyLabel(default_dir, self.exportSection)
        self.outputDirLabel.setObjectName('outputDirLabel')
        outDirRow.addWidget(self.outputDirLabel, 1)

        self.btnBrowseDir = PushButton(
            self.tr('浏览...'), self.exportSection, icon=FluentIcon.FOLDER)
        self.btnBrowseDir.clicked.connect(self._onBrowseOutputDir)
        outDirRow.addWidget(self.btnBrowseDir)
        layout.addLayout(outDirRow)

        # 导出按钮行
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

    # -------- 导出：单张 --------
    def _onSaveSingle(self, result: dict):
        folder = self._getOutputDir()
        prefix = self._getPrefix() or 'converted_'
        ext = result['target_format'].lower()
        base = Path(result['file_name']).stem
        suggested = os.path.join(folder, f"{prefix}{base}.{ext}")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存图片'),
            suggested,
            f"{result['target_format']} (*.{ext})")
        if save_path:
            save_result_to_path(result, save_path)

    # -------- 导出：全部 --------
    def _onSaveAll(self):
        if not self.conversion_results:
            return
        folder = self._getOutputDir()
        prefix = self._getPrefix() or 'converted_'
        save_all_results(self.conversion_results, folder, prefix)

        InfoBar.success(
            title=self.tr('导出完成'),
            content=self.tr('已保存 {} 张图片到: {}').format(
                len(self.conversion_results), folder),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    # -------- 导出：ZIP --------
    def _onSaveZip(self):
        if not self.conversion_results:
            return

        target_folder = self._getOutputDir()
        default_name = os.path.join(target_folder, 'converted_images.zip')
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('保存为 ZIP'),
            default_name,
            'ZIP (*.zip)')
        if not save_path:
            return

        prefix = self._getPrefix() or 'converted_'
        save_results_as_zip(self.conversion_results, save_path, prefix)

        InfoBar.success(
            title=self.tr('导出完成'),
            content=self.tr('ZIP 已保存到: {}').format(save_path),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )
