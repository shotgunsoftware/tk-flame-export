# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog.ui'
#
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from tank.platform.qt import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(568, 285)
        self.gridLayout = QtGui.QGridLayout(Dialog)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtGui.QLabel(Dialog)
        self.label.setWordWrap(True)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.label_3 = QtGui.QLabel(Dialog)
        self.label_3.setText("")
        self.label_3.setPixmap(QtGui.QPixmap(":/res/logo.png"))
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.gridLayout.addLayout(self.verticalLayout, 0, 0, 1, 1)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtGui.QSpacerItem(368, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.cancel = QtGui.QPushButton(Dialog)
        self.cancel.setObjectName("cancel")
        self.horizontalLayout.addWidget(self.cancel)
        self.submit = QtGui.QPushButton(Dialog)
        self.submit.setObjectName("submit")
        self.horizontalLayout.addWidget(self.submit)
        self.gridLayout.addLayout(self.horizontalLayout, 1, 0, 1, 2)
        self.comments = QtGui.QPlainTextEdit(Dialog)
        self.comments.setMinimumSize(QtCore.QSize(300, 100))
        self.comments.setObjectName("comments")
        self.gridLayout.addWidget(self.comments, 0, 1, 1, 1)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Submit to Shotgun", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Dialog", "This will submit your selected sequences for review in Shotgun. Quicktimes will be generated for each sequence and uploaded to Shotgun. \n"
"\n"
"Please enter a description of your review submission.", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel.setText(QtGui.QApplication.translate("Dialog", "Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.submit.setText(QtGui.QApplication.translate("Dialog", "Submit to Shotgun", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
