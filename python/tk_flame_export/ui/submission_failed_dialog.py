# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'submission_failed_dialog.ui'
#
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from tank.platform.qt import QtCore, QtGui

class Ui_SubmissionFailedDialog(object):
    def setupUi(self, SubmissionFailedDialog):
        SubmissionFailedDialog.setObjectName("SubmissionFailedDialog")
        SubmissionFailedDialog.resize(477, 149)
        self.verticalLayout = QtGui.QVBoxLayout(SubmissionFailedDialog)
        self.verticalLayout.setContentsMargins(20, -1, 20, -1)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_2 = QtGui.QLabel(SubmissionFailedDialog)
        self.label_2.setText("")
        self.label_2.setPixmap(QtGui.QPixmap(":/tk-flame-export/submission_failed.png"))
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtGui.QSpacerItem(368, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.submit = QtGui.QPushButton(SubmissionFailedDialog)
        self.submit.setObjectName("submit")
        self.horizontalLayout.addWidget(self.submit)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(SubmissionFailedDialog)
        QtCore.QMetaObject.connectSlotsByName(SubmissionFailedDialog)

    def retranslateUi(self, SubmissionFailedDialog):
        SubmissionFailedDialog.setWindowTitle(QtGui.QApplication.translate("SubmissionFailedDialog", "Shotgun Submission Failed", None, QtGui.QApplication.UnicodeUTF8))
        self.submit.setText(QtGui.QApplication.translate("SubmissionFailedDialog", "Ok", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
