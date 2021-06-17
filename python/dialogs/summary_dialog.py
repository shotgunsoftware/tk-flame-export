# Copyright (c) 2014 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import absolute_import

import sys

from sgtk.platform.qt import QtGui

if sys.version_info.major == 2:
    from .ui_python2.submission_complete_dialog import Ui_SubmissionCompleteDialog
    from .ui_python2.submission_failed_dialog import Ui_SubmissionFailedDialog
else:
    from .ui.submission_complete_dialog import Ui_SubmissionCompleteDialog
    from .ui.submission_failed_dialog import Ui_SubmissionFailedDialog


class SubmissionCompleteDialog(QtGui.QWidget):
    """
    Summary dialog popping up after a Shot export has completed.
    """

    def __init__(self, message):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)

        # now load in the UI that was created in the UI designer
        self.ui = Ui_SubmissionCompleteDialog()
        self.ui.setupUi(self)

        self.ui.status.setText(message)

        # with the tk dialogs, we need to hook up our modal
        # dialog signals in a special way
        self.__exit_code = QtGui.QDialog.Rejected
        self.ui.submit.clicked.connect(self._on_submit_clicked)

    @property
    def exit_code(self):
        """
        Used to pass exit code back though sgtk dialog

        :returns:    The dialog exit code
        """
        return self.__exit_code

    @property
    def hide_tk_title_bar(self):
        """
        Tell the system to not show the std toolbar.
        """
        return True

    def _on_submit_clicked(self):
        """
        Called when the 'submit' button is clicked.
        """
        self.__exit_code = QtGui.QDialog.Accepted
        self.close()


class SubmissionFailedDialog(QtGui.QWidget):
    """
    Summary dialog popping up when a Shot export fails.
    """

    def __init__(self, log_file):
        """
        Constructor
        """
        # first, call the base class and let it do its thing.
        QtGui.QWidget.__init__(self)

        # now load in the UI that was created in the UI designer
        self.ui = Ui_SubmissionFailedDialog()
        self.ui.setupUi(self)
        self.ui.status.setText(
            "<html><head/><body><p>"
            "Either the export was cancelled along the way or an error occurred. "
            "No content will be pushed to Shotgun this time. <br/><br/>For more details, please see the log file "
            "<span style=\" font-family:'Courier New,courier';\">%s</span></p></body></html>"
            % log_file
        )

        # with the tk dialogs, we need to hook up our modal
        # dialog signals in a special way
        self.__exit_code = QtGui.QDialog.Rejected
        self.ui.submit.clicked.connect(self._on_submit_clicked)

    @property
    def exit_code(self):
        """
        Used to pass exit code back though sgtk dialog

        :returns:    The dialog exit code
        """
        return self.__exit_code

    @property
    def hide_tk_title_bar(self):
        """
        Tell the system to not show the std toolbar.
        """
        return True

    def _on_submit_clicked(self):
        """
        Called when the 'submit' button is clicked.
        """
        self.__exit_code = QtGui.QDialog.Accepted
        self.close()
