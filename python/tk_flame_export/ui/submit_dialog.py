# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'submit_dialog.ui'
#
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from tank.platform.qt import QtCore, QtGui

class Ui_SubmitDialog(object):
    def setupUi(self, SubmitDialog):
        SubmitDialog.setObjectName("SubmitDialog")
        SubmitDialog.resize(487, 529)
        self.verticalLayout = QtGui.QVBoxLayout(SubmitDialog)
        self.verticalLayout.setContentsMargins(20, 20, 20, -1)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_2 = QtGui.QLabel(SubmitDialog)
        self.label_2.setText("")
        self.label_2.setPixmap(QtGui.QPixmap(":/tk-flame-export/ui_splash.png"))
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.comments = QtGui.QPlainTextEdit(SubmitDialog)
        self.comments.setMinimumSize(QtCore.QSize(300, 100))
        self.comments.setObjectName("comments")
        self.verticalLayout.addWidget(self.comments)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtGui.QSpacerItem(368, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.cancel = QtGui.QPushButton(SubmitDialog)
        self.cancel.setObjectName("cancel")
        self.horizontalLayout.addWidget(self.cancel)
        self.submit = QtGui.QPushButton(SubmitDialog)
        self.submit.setObjectName("submit")
        self.horizontalLayout.addWidget(self.submit)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(SubmitDialog)
        QtCore.QMetaObject.connectSlotsByName(SubmitDialog)

    def retranslateUi(self, SubmitDialog):
        SubmitDialog.setWindowTitle(QtGui.QApplication.translate("SubmitDialog", "Submit to Shotgun", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel.setText(QtGui.QApplication.translate("SubmitDialog", "Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.submit.setText(QtGui.QApplication.translate("SubmitDialog", "Submit to Shotgun", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
