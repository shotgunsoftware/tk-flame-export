# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'submission_failed_dialog.ui'
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

class Ui_SubmissionFailedDialog(object):
    def setupUi(self, SubmissionFailedDialog):
        if not SubmissionFailedDialog.objectName():
            SubmissionFailedDialog.setObjectName("SubmissionFailedDialog")
        SubmissionFailedDialog.resize(491, 204)
        self.verticalLayout = QVBoxLayout(SubmissionFailedDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(20, -1, 20, -1)
        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.label_2 = QLabel(SubmissionFailedDialog)
        self.label_2.setObjectName("label_2")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        self.label_2.setPixmap(QPixmap(":/tk-flame-export/failure.png"))

        self.horizontalLayout_3.addWidget(self.label_2)

        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label_3 = QLabel(SubmissionFailedDialog)
        self.label_3.setObjectName("label_3")
        self.label_3.setStyleSheet("QLabel { font-size: 18px; }")
        self.label_3.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.verticalLayout_3.addWidget(self.label_3)

        self.status = QLabel(SubmissionFailedDialog)
        self.status.setObjectName("status")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.status.sizePolicy().hasHeightForWidth())
        self.status.setSizePolicy(sizePolicy1)
        self.status.setTextFormat(Qt.RichText)
        self.status.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.status.setWordWrap(True)

        self.verticalLayout_3.addWidget(self.status)


        self.horizontalLayout_3.addLayout(self.verticalLayout_3)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalSpacer = QSpacerItem(368, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.submit = QPushButton(SubmissionFailedDialog)
        self.submit.setObjectName("submit")

        self.horizontalLayout.addWidget(self.submit)


        self.verticalLayout.addLayout(self.horizontalLayout)


        self.retranslateUi(SubmissionFailedDialog)

        QMetaObject.connectSlotsByName(SubmissionFailedDialog)
    # setupUi

    def retranslateUi(self, SubmissionFailedDialog):
        SubmissionFailedDialog.setWindowTitle(QCoreApplication.translate("SubmissionFailedDialog", "ShotGrid Submission Failed", None))
        self.label_2.setText("")
        self.label_3.setText(QCoreApplication.translate("SubmissionFailedDialog", "Something went wrong!", None))
        self.status.setText("")
        self.submit.setText(QCoreApplication.translate("SubmissionFailedDialog", "Ok", None))
    # retranslateUi

