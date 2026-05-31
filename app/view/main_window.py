# coding: utf-8
from typing import List
from PySide6.QtCore import Qt, Signal, QEasingCurve, QUrl, QSize, QTimer
from PySide6.QtGui import QIcon, QDesktopServices, QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QFrame, QWidget

# [test]
from qfluentwidgets import (NavigationAvatarWidget, NavigationItemPosition, MessageBox, FluentWindow,
                            SplashScreen, SystemThemeListener, isDarkTheme, SubtitleLabel, setFont,
                            MSFluentWindow)
from qfluentwidgets import FluentIcon as FIF

from .gallery_interface import GalleryInterface
from .home_interface import HomeInterface
from .gif_interface import GifInterface
from .basic_input_interface import BasicInputInterface
from .icon_interface import IconInterface
from .setting_interface import SettingInterface
from ..common.config import ZH_SUPPORT_URL, EN_SUPPORT_URL, cfg
from ..common.icon import Icon
from ..common.signal_bus import signalBus
from ..common.translator import Translator
from ..resources import resources_rc
from ..components.about_dialog import AboutDialog

# [test]
class TempWidget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)

        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)

        # 必须给子界面设置全局唯一的对象名
        self.setObjectName(text.replace(' ', '-'))

class MainWindow(MSFluentWindow):

    def __init__(self):
        super().__init__()
        self.initWindow()

        # create system theme listener
        self.themeListener = SystemThemeListener(self)

        # create sub interface
        self.homeInterface = HomeInterface(self)
        self.gifInterface = GifInterface(self)
        self.iconInterface = IconInterface(self)
        self.basicInputInterface = BasicInputInterface(self)
        self.settingInterface = SettingInterface(self)

        # [test]
        self.tempInterface1 = TempWidget('Home Interface', self)
        self.tempInterface2 = TempWidget('Music Interface', self)

        self.connectSignalToSlot()

        # add items to navigation interface
        self.initNavigation()
        self.splashScreen.finish() 

        # start theme listener
        self.themeListener.start()

    def connectSignalToSlot(self):
        signalBus.micaEnableChanged.connect(self.setMicaEffectEnabled)
        signalBus.switchToSampleCard.connect(self.switchToSample)
        signalBus.supportSignal.connect(self.onSupport)

    def initNavigation(self):
        # add navigation items
        t = Translator()

        # [test] 谁在顶部，谁第一个显示
        # Top
        self.addSubInterface(self.homeInterface, FIF.HOME, self.tr('Convert'), FIF.HOME)
        self.addSubInterface(self.gifInterface, FIF.VIDEO, self.tr('GIF'), FIF.VIDEO)
        self.addSubInterface(self.iconInterface, Icon.EMOJI_TAB_SYMBOLS, t.icons, Icon.EMOJI_TAB_SYMBOLS)

        # Scroll
        self.addSubInterface(self.basicInputInterface, FIF.CHECKBOX, t.basicInput, FIF.CHECKBOX, NavigationItemPosition.SCROLL)
        # [test]
        self.addSubInterface(self.tempInterface1, FIF.SETTING, 'Settings1', FIF.SETTING, NavigationItemPosition.SCROLL)
        self.addSubInterface(self.tempInterface2, FIF.SETTING, 'Settings2', FIF.SETTING, NavigationItemPosition.SCROLL)

        # Bottom
        self.navigationInterface.addItem(
            routeKey='about',
            icon=Icon.PRICE,
            text=self.tr('About'),
            onClick=self.onAbout,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )
        self.addSubInterface(self.settingInterface, FIF.SETTING, self.tr('Settings'), FIF.SETTING, NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(960, 780)
        self.setMinimumWidth(760)
        self.setWindowIcon(QIcon(':/gallery/images/river.png'))
        self.setWindowTitle('River')

        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))
        
        # apply window sticky at startup
        self.setStayOnTop(cfg.get(cfg.windowSticky))

        # create splash screen
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(180, 180))
        self.splashScreen.raise_()

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        self.show()
        QApplication.processEvents()

    def onAbout(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def onSupport(self):
        language = cfg.get(cfg.language).value
        if language.name() == "zh_CN":
            QDesktopServices.openUrl(QUrl(ZH_SUPPORT_URL))
        else:
            QDesktopServices.openUrl(QUrl(EN_SUPPORT_URL))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen'):
            self.splashScreen.resize(self.size())

    def closeEvent(self, e):
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        super().closeEvent(e)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()

        # retry
        if self.isMicaEffectEnabled():
            QTimer.singleShot(100, lambda: self.windowEffect.setMicaEffect(self.winId(), isDarkTheme()))

    def switchToSample(self, routeKey, index):
        """ switch to sample """
        interfaces = self.findChildren(GalleryInterface)
        for w in interfaces:
            if w.objectName() == routeKey:
                self.stackedWidget.setCurrentWidget(w, popOut=True) # 切换页面，是否显示弹出动画效果
                w.scrollToCard(index)
