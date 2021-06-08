# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'batch_render_dialog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

try:
    from tank.platform.qt.QtCore import *
except ImportError:
    from PySide2.QtCore import *
try:
    from tank.platform.qt.QtGui import *
except ImportError:
    from PySide2.QtGui import *
try:
    from tank.platform.qt.QtWidgets import *
except ImportError:
    from PySide2.QtWidgets import *

from  . import resources_rc

class Ui_BatchRenderDialog(object):
    def setupUi(self, BatchRenderDialog):
        if not BatchRenderDialog.objectName():
            BatchRenderDialog.setObjectName("BatchRenderDialog")
        BatchRenderDialog.resize(352, 398)
        self.verticalLayout = QVBoxLayout(BatchRenderDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(20, 20, 20, -1)
        self.label_2 = QLabel(BatchRenderDialog)
        self.label_2.setObjectName("label_2")
        self.label_2.setPixmap(QPixmap(":/tk-flame-export/batch_render_splash.png"))

        self.verticalLayout.addWidget(self.label_2)

        self.comments = QPlainTextEdit(BatchRenderDialog)
        self.comments.setObjectName("comments")
        self.comments.setMinimumSize(QSize(300, 100))

        self.verticalLayout.addWidget(self.comments)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(4)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalSpacer = QSpacerItem(368, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.cancel = QPushButton(BatchRenderDialog)
        self.cancel.setObjectName("cancel")

        self.horizontalLayout.addWidget(self.cancel)

        self.submit = QPushButton(BatchRenderDialog)
        self.submit.setObjectName("submit")

        self.horizontalLayout.addWidget(self.submit)


        self.verticalLayout.addLayout(self.horizontalLayout)


        self.retranslateUi(BatchRenderDialog)

        QMetaObject.connectSlotsByName(BatchRenderDialog)
    # setupUi

    def retranslateUi(self, BatchRenderDialog):
        BatchRenderDialog.setWindowTitle(QCoreApplication.translate("BatchRenderDialog", "Submit to ShotGrid", None))
        self.label_2.setText("")
        self.cancel.setText(QCoreApplication.translate("BatchRenderDialog", "Skip", None))
        self.submit.setText(QCoreApplication.translate("BatchRenderDialog", "Send to ShotGrid Review", None))
    # retranslateUi

