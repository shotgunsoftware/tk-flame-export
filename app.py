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
import uuid
import os
import platform

from sgtk.platform import Application


class FlameExport(Application):
    """
    Export functionality to automate and streamline content export out of Flame.
    """
    
    def init_app(self):
        """
        Called as the application is being initialized.
        """
        self.log_debug("%s: Initializing" % self)
        self._sessions = {}        
        
    def get_export_presets(self):
        """
        Returns the different presets defined in the configuration.
        
        :returns: List of tuples - (preset title, preset name)
        """
        presets = []
        presets.append(("Shotgun Sequence Export", "sequence_export"))
        presets.append(("Shotgun Sequence Export 2", "sequence_export_2"))
        return presets
    
    def create_export_session(self, preset):
        """
        Start a new export session.
        Creates a session object which represents a single export session in flame.
        
        :returns: session id string which is later passed into various methods
        """
        session_id = "tk_%s" % uuid.uuid4().hex
        tk_flame_export = self.import_module("tk_flame_export")
        self._sessions[session_id] = tk_flame_export.ExportSession(preset)
        return session_id
    
    def _resolve_session(self, session_id):
        """
        Helper method which validates and reuturns a session id
        
        :param session_id: Export session id, as created by create_export_session
        :returns: An ExportSession object
        """
        if session_id not in self._sessions:
            raise TankError("Export session %s not associated with app %s!" % (session_id, self))
        return self._sessions[session_id]
    
    def get_destination_host(self, session_id):
        """
        Returns the host to which the export is routed to.
        
        :param session_id: String which identifies which export session is being referred to
        :returns: host for export
        """
        # hard coded to localhost for now
        return "localhost"
    
    def get_destination_path(self, session_id):
        """
        Returns the base path for the export 
        
        :param session_id: String which identifies which export session is being referred to
        :returns: full path string
        """        
        return self._resolve_session(session_id).get_destination_path()
        
    def get_export_preset_path(self, session_id):
        """
        Returns a path to an xml export profile 
        
        :param session_id: String which identifies which export session is being referred to
        :return: full path string
        """
        return self._resolve_session(session_id).get_export_preset_path()
        
    def prepare_export_structure(self, session_id, sequence_name, shot_names):
        """
        Called from the flame hooks before export.
        This is the time to set up the structure in Shotgun.
        
        :param session_id: String which identifies which export session is being referred to
        :param sequence_name: The sequence that is being exported
        :param shot_name: list of shots to be exported
        """
        return self._resolve_session(session_id).prepare_export_structure(sequence_name, shot_names)        
        
    def use_backburner_post_events(self):
        """
        Controls if events should be routed via the render farm
        
        :returns: true if renderfarm is used, false if not
        """
        return False
        
    def register_publish(self, session_id, info):
        """
        Called when an item has been exported
        
        :param session_id: String which identifies which export session is being referred to
        :param info: metadata dictionary for the publish
        """        
        return self._resolve_session(session_id).register_publish(info)
        
    def post_process_export(self, session_id):
        """
        Called when an export has completed
        
        :param session_id: String which identifies which export session is being referred to
        """
        return self._resolve_session(session_id).post_process_export()
        
        
