# coding:utf-8
import json

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea, isDarkTheme, FluentIcon
from ..common.config import cfg, HELP_URL, REPO_URL, EXAMPLE_URL, FEEDBACK_URL
from ..common.icon import Icon, FluentIconBase
from ..components.link_card import LinkCardView
from ..components.sample_card import SampleCardView
from ..common.style_sheet import StyleSheet


class BannerWidget(QWidget):
    """ Banner widget """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(336)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel('River', self)
        self.banner = QPixmap(':/gallery/images/header1.png')
        self.linkCardView = LinkCardView(self)

        self.galleryLabel.setObjectName('galleryLabel')

        self.vBoxLayout.setSpacing(0) # 元素间距
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addWidget(self.linkCardView, 1, Qt.AlignBottom)
        self.vBoxLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.linkCardView.addCard(
            ':/gallery/images/river.png',
            self.tr('Getting started'),
            self.tr('An overview of app development options and samples.'),
            HELP_URL
        )

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            self.tr('GitHub repo'),
            self.tr(
                'The latest fluent design controls and styles for your applications.'),
            REPO_URL
        )

        self.linkCardView.addCard(
            FluentIcon.CODE,
            self.tr('Code samples'),
            self.tr(
                'Find samples that demonstrate specific tasks, features and APIs.'),
            EXAMPLE_URL
        )

        self.linkCardView.addCard(
            FluentIcon.FEEDBACK,
            self.tr('Send feedback'),
            self.tr('Help us improve PyQt-Fluent-Widgets by providing feedback.'),
            FEEDBACK_URL
        )

        # self.linkCardView.addCard(
        #     FluentIcon.FEEDBACK,
        #     self.tr('Send feedback'),
        #     self.tr('Help us improve PyQt-Fluent-Widgets by providing feedback.'),
        #     FEEDBACK_URL
        # )

        # self.linkCardView.addCard(
        #     FluentIcon.FEEDBACK,
        #     self.tr('Send feedback'),
        #     self.tr('Help us improve PyQt-Fluent-Widgets by providing feedback.'),
        #     FEEDBACK_URL
        # )

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        w, h = self.width(), self.height()
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h-50, 50, 50))
        path.addRect(QRectF(w-50, 0, 50, 50))
        path.addRect(QRectF(w-50, h-50, 50, 50))
        path = path.simplified()

        # init linear gradient effect
        gradient = QLinearGradient(0, 0, 0, h)

        # draw background color
        if not isDarkTheme():
            gradient.setColorAt(0, QColor(207, 216, 228, 255))
            gradient.setColorAt(1, QColor(207, 216, 228, 0))
        else:
            gradient.setColorAt(0, QColor(0, 0, 0, 255))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.fillPath(path, QBrush(gradient))

        # draw banner image
        pixmap = self.banner.scaled(
            self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        painter.fillPath(path, QBrush(pixmap))


class HomeInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()
        self.loadSamples()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('homeInterface')
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def loadSamples(self):
        """ load samples """
        # basic input samples
        basicInputView = SampleCardView(
            self.tr("Basic input samples"), self.view)
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/Button.png",
            title="Button",
            content=self.tr(
                "A control that responds to user input and emit clicked signal."),
            routeKey="basicInputInterface",
            index=0
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/Checkbox.png",
            title="CheckBox",
            content=self.tr("A control that a user can select or clear."),
            routeKey="basicInputInterface",
            index=8
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/ComboBox.png",
            title="ComboBox",
            content=self.tr(
                "A drop-down list of items a user can select from."),
            routeKey="basicInputInterface",
            index=10
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/DropDownButton.png",
            title="DropDownButton",
            content=self.tr(
                "A button that displays a flyout of choices when clicked."),
            routeKey="basicInputInterface",
            index=12
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/HyperlinkButton.png",
            title="HyperlinkButton",
            content=self.tr(
                "A button that appears as hyperlink text, and can navigate to a URI or handle a Click event."),
            routeKey="basicInputInterface",
            index=18
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/RadioButton.png",
            title="RadioButton",
            content=self.tr(
                "A control that allows a user to select a single option from a group of options."),
            routeKey="basicInputInterface",
            index=19
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/Slider.png",
            title="Slider",
            content=self.tr(
                "A control that lets the user select from a range of values by moving a Thumb control along a track."),
            routeKey="basicInputInterface",
            index=20
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/SplitButton.png",
            title="SplitButton",
            content=self.tr(
                "A two-part button that displays a flyout when its secondary part is clicked."),
            routeKey="basicInputInterface",
            index=21
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/ToggleSwitch.png",
            title="SwitchButton",
            content=self.tr(
                "A switch that can be toggled between 2 states."),
            routeKey="basicInputInterface",
            index=25
        )
        basicInputView.addSampleCard(
            icon=":/gallery/images/controls/ToggleButton.png",
            title="ToggleButton",
            content=self.tr(
                "A button that can be switched between two states like a CheckBox."),
            routeKey="basicInputInterface",
            index=26
        )
        self.vBoxLayout.addWidget(basicInputView)

