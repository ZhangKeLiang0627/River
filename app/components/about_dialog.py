# coding:utf-8
from PySide6.QtCore import Qt, Signal, QUrl, QDate, qVersion
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget, QHBoxLayout

from qfluentwidgets import IconWidget, FluentIcon, MessageBoxBase, SubtitleLabel, BodyLabel, TransparentPushButton, __version__
from ..common.style_sheet import StyleSheet
from ..common.config import cfg

class AboutDialog(MessageBoxBase):
    def __init__(self, parent = None):
        super().__init__(parent)

        self.initWidget()

    def initWidget(self):
        appName = cfg.appName
        appVersion = cfg.appVersion
        year = QDate.currentDate().year()

        self.titleLabel = SubtitleLabel(self.tr("About {app_name}").format(app_name = appName), self)
        self.appVersionLabel = BodyLabel(self.tr("Version {app_version}").format(app_version = appVersion), self)
        self.qtVersionLabel = BodyLabel(self.tr("Powered by Qt {qt_version} and QFluentWidgets {qfluentwidgets_version}").format(qt_version = qVersion(), qfluentwidgets_version = __version__), self)
        self.licenseLabel = BodyLabel(self.tr("This software is free and open-source, licensed under the GNU General Public License v3 (GPLv3)."))
        self.copyrightLabel = BodyLabel(self.tr("Copyright © 2025-{year} kkl. All Rights Reserved.").format(year = year))
        self.sponsorLabel = BodyLabel(self.tr("If this project saved you time or solved your problem, consider buying the author a coffee! Don't forget to star the repository on GitHub to support open-source development."))
        self.sponsorLabel.setWordWrap(True)

        contentLayout = QVBoxLayout()
        contentLayout.setContentsMargins(0, 0, 0, 0)
        contentLayout.setSpacing(0)
        contentLayout.addWidget(self.appVersionLabel)
        contentLayout.addWidget(self.qtVersionLabel)
        contentLayout.addSpacing(10)
        contentLayout.addWidget(self.licenseLabel)
        contentLayout.addSpacing(10)
        contentLayout.addWidget(self.copyrightLabel)
        contentLayout.addSpacing(30)
        contentLayout.addWidget(self.sponsorLabel)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addLayout(contentLayout)

        self.hideCancelButton()
        self.widget.setMinimumWidth(600)
        # self.widget.setFixedWidth(600)
        self._connectSignalToSlot()

    def _connectSignalToSlot(self):
        pass
        
    # Override
    # @brief Override keyPressEvent to close the dialog when pressing the Escape key.
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)