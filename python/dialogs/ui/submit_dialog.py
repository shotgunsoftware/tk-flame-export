# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'submit_dialog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from tank.platform.qt import QtCore
for name, cls in QtCore.__dict__.items():
    if isinstance(cls, type): globals()[name] = cls

from tank.platform.qt import QtGui
for name, cls in QtGui.__dict__.items():
    if isinstance(cls, type): globals()[name] = cls


from  . import resources_rc

class Ui_SubmitDialog(object):
    def setupUi(self, SubmitDialog):
        if not SubmitDialog.objectName():
            SubmitDialog.setObjectName(u"SubmitDialog")
        SubmitDialog.resize(487, 577)
        self.verticalLayout = QVBoxLayout(SubmitDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_2 = QLabel(SubmitDialog)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setPixmap(QPixmap(u":/tk-flame-export/ui_splash.png"))

        self.verticalLayout.addWidget(self.label_2)

        self.comments = QPlainTextEdit(SubmitDialog)
        self.comments.setObjectName(u"comments")
        self.comments.setMinimumSize(QSize(300, 100))

        self.verticalLayout.addWidget(self.comments)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label = QLabel(SubmitDialog)
        self.label.setObjectName(u"label")

        self.horizontalLayout_2.addWidget(self.label)

        self.export_presets = QComboBox(SubmitDialog)
        self.export_presets.setObjectName(u"export_presets")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.export_presets.sizePolicy().hasHeightForWidth())
        self.export_presets.setSizePolicy(sizePolicy)

        self.horizontalLayout_2.addWidget(self.export_presets)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer = QSpacerItem(368, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.cancel = QPushButton(SubmitDialog)
        self.cancel.setObjectName(u"cancel")

        self.horizontalLayout.addWidget(self.cancel)

        self.submit = QPushButton(SubmitDialog)
        self.submit.setObjectName(u"submit")

        self.horizontalLayout.addWidget(self.submit)

        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(SubmitDialog)

        QMetaObject.connectSlotsByName(SubmitDialog)
    # setupUi

    def retranslateUi(self, SubmitDialog):
        SubmitDialog.setWindowTitle(QCoreApplication.translate("SubmitDialog", u"Submit to Flow Production Tracking", None))
        self.label_2.setText("")
        self.label.setText(QCoreApplication.translate("SubmitDialog", u"Use Export Preset", None))
        self.cancel.setText(QCoreApplication.translate("SubmitDialog", u"Cancel", None))
        self.submit.setText(QCoreApplication.translate("SubmitDialog", u"Submit to Flow Production Tracking", None))
    # retranslateUi
