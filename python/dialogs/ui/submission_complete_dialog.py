# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'submission_complete_dialog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from tank.platform.qt.QtCore import *
from tank.platform.qt.QtGui import *
from tank.platform.qt.QtWidgets import *

from  . import resources_rc

class Ui_SubmissionCompleteDialog(object):
    def setupUi(self, SubmissionCompleteDialog):
        if not SubmissionCompleteDialog.objectName():
            SubmissionCompleteDialog.setObjectName(u"SubmissionCompleteDialog")
        SubmissionCompleteDialog.resize(569, 237)
        self.verticalLayout = QVBoxLayout(SubmissionCompleteDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(20, -1, 20, -1)
        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label = QLabel(SubmissionCompleteDialog)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setPixmap(QPixmap(u":/tk-flame-export/success.png"))
        self.label.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.horizontalLayout_3.addWidget(self.label)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_3 = QLabel(SubmissionCompleteDialog)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setStyleSheet(u"QLabel { font-size: 18px; }")
        self.label_3.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)

        self.verticalLayout_2.addWidget(self.label_3)

        self.status = QLabel(SubmissionCompleteDialog)
        self.status.setObjectName(u"status")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.status.sizePolicy().hasHeightForWidth())
        self.status.setSizePolicy(sizePolicy1)
        self.status.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.status.setWordWrap(True)

        self.verticalLayout_2.addWidget(self.status)


        self.horizontalLayout_3.addLayout(self.verticalLayout_2)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer = QSpacerItem(368, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.submit = QPushButton(SubmissionCompleteDialog)
        self.submit.setObjectName(u"submit")

        self.horizontalLayout.addWidget(self.submit)


        self.verticalLayout.addLayout(self.horizontalLayout)


        self.retranslateUi(SubmissionCompleteDialog)

        QMetaObject.connectSlotsByName(SubmissionCompleteDialog)
    # setupUi

    def retranslateUi(self, SubmissionCompleteDialog):
        SubmissionCompleteDialog.setWindowTitle(QCoreApplication.translate("SubmissionCompleteDialog", u"Shotgun Submission Complete", None))
        self.label.setText("")
        self.label_3.setText(QCoreApplication.translate("SubmissionCompleteDialog", u"Submission Complete!", None))
        self.status.setText(QCoreApplication.translate("SubmissionCompleteDialog", u"TextLabel", None))
        self.submit.setText(QCoreApplication.translate("SubmissionCompleteDialog", u"Ok", None))
    # retranslateUi

