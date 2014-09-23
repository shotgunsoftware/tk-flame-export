# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Flame content exporter.
"""

import sys
import os
import platform

from sgtk.platform import Application

class FlameExport(Application):
    
    def init_app(self):
        """
        Called as the application is being initialized
        """
        self.log_debug("%s: Initializing" % self)

    def get_export_presents(self):
        """
        Placeholder
        """
        return ["Shotgun Sequence Export", "Shotgun Other Sequence Export"]
    
    
        
