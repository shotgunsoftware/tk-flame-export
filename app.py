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

import uuid
import os
import re
import xml.etree.ElementTree
import sgtk
import datetime

from sgtk import TankError
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
        
        tk_flame_export = self.import_module("tk_flame_export")
        self._sg_submit_helper = tk_flame_export.ShotgunSubmitter()
        
        # shot metadata
        self._shots = {}
        
        # batch render tracking
        self._send_batch_render_to_review = False
        
        # UI comments
        self._user_comments = ""
        
        # flag to indicate that something was actually submitted
        self._submission_done = False
        
        # register our desired interaction with flame hooks
        menu_caption = self.get_setting("menu_name")
        
        # set up callbacks for the engine to trigger 
        # when this profile is being triggered 
        callbacks = {}
        callbacks["preCustomExport"] = self.pre_custom_export
        callbacks["preExportSequence"] = self.pre_export_sequence
        callbacks["preExportAsset"] = self.pre_export_asset
        callbacks["postExportAsset"] = self.submit_post_asset_backburner_job
        callbacks["postCustomExport"] = self.update_cut_and_display_summary
        self.engine.register_export_hook(menu_caption, callbacks)
        
        # also register this app so that it runs after export
        batch_callbacks = {}
        batch_callbacks["batchExportEnd"] = self.submit_post_batch_backburner_job
        batch_callbacks["batchExportBegin"] = self.pre_batch_render_checks
        self.engine.register_batch_hook(batch_callbacks)
        


    def pre_custom_export(self, session_id, info):
        """
        Hook called before a custom export begins. The export will be blocked
        until this function returns. This can be used to fill information that would
        have normally been extracted from the export window.
        
        :param info: Dictionary with info about the export. Contains the keys
                     - destinationHost: Host name where the exported files will be written to.
                     - destinationPath: Export path root.
                     - presetPath: Path to the preset used for the export.
                     - abort: Pass True back to flame if you want to abort
                     - abortMessage: Abort message to feed back to client
        """
        
        from PySide import QtGui, QtCore
        
        # reset export session data
        self._shots = {}
        self._submission_done = False
        
        # pop up a UI asking the user for description
        tk_flame_export = self.import_module("tk_flame_export")        
        (return_code, widget) = self.engine.show_modal("Export Shots", self, tk_flame_export.SubmitDialog)
        
        if return_code == QtGui.QDialog.Rejected:
            # user pressed cancel
            info["abort"] = True
            info["abortMessage"] = "User cancelled the operation."
                   
        else:
            # get comments from user
            self._user_comments = widget.get_comments()
            # populate the host to use for the export. Currently hard coded to local
            info["destinationHost"] = self.engine.get_server_hostname()
            # let the export root path align with the primary project root
            info["destinationPath"] = self.sgtk.project_path
            # pick up the xml export profile from the configuration
            flame_templates = self.__resolve_flame_templates()
            preset_xml_path = self.execute_hook_method("settings_hook", 
                                                       "get_export_preset",
                                                       resolved_flame_templates=flame_templates)
                        
            # tell flame about it
            info["presetPath"] = preset_xml_path
            
            self.log_debug("%s: Starting custom export session with preset '%s'" % (self, info["presetPath"]))
        
 
#     This doesn't seem to be needed at the moment, but may came in handy later...
#
#     def __resolve_profile_start_frame(self, profile_xml_path):
#         """
#         Given an export xml file, return start frame and handle parameters
#         
#         :param profile_xml_path: path to xml settings file
#         :returns: start frame for all image sequences, as defined in the export preset.
#         """
#         fh = open(profile_xml_path, "rt")
#         try:
#             xml_content = fh.read()
#         finally:
#             fh.close()
#         
#         root = xml.etree.ElementTree.fromstring(xml_content)
#         
#         start_frame_nodes = root.findall("./name/startFrame")
#         if len(start_frame_nodes) == 0:
#             raise TankError("Could not find start frame node in %s" % profile_xml_path)
#         start_frame_str = start_frame_nodes[0].text
#         start_frame = int(start_frame_str)
#         
#         handle_nodes = root.findall("./sequence/videoMedia/nbHandles")
#         if len(handle_nodes) == 0:
#             raise TankError("Could not find video handle frame node in %s" % profile_xml_path)
#         handle_node_str = handle_nodes[0].text
#         handle = int(handle_node_str)
#         
#         return (start_frame, handle)
        

    def __resolve_flame_templates(self):
        """
        Convert the toolkit templates defined in the app settings to 
        Flame equivalents.
        
        :returns: Dictionary of flame template definition strings, keyed by
                  the same names as are being used for the templates in the app settings.
        """
        # now we need to take our toolkit templates and inject them into the xml template
        # definition that we are about to send to Flame.
        #
        # typically, our template defs will look something like this:
        # plate:        'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        # batch:        'sequences/{Sequence}/{Shot}/editorial/flame/batch/{Shot}.v{version}.batch'
        # segment_clip: 'sequences/{Sequence}/{Shot}/editorial/flame/sources/{segment_name}.clip'
        # shot_clip:    'sequences/{Sequence}/{Shot}/editorial/flame/{Shot}.clip'
        #
        # {Sequence} may be {Scene} or {CustomEntityXX} according to the configuration and the 
        # exact entity type to use is passed into the hook via the the shot_parent_entity_type setting.
        #
        # The flame export root is set to correspond to the toolkit project, meaning that both the 
        # flame and toolkit templates share the same root point.
        #
        # The following replacements will be made to convert the toolkit template into Flame equivalents:
        # 
        # {Sequence}     ==> <name> (Note: May be {Scene} or {CustomEntityXX} according to the configuration)
        # {Shot}         ==> <shot name>
        # {segment_name} ==> <segment name>
        # {version}      ==> <version>
        # {SEQ}          ==> <frame>
        # 
        # and the special one <ext> which corresponds to the last part of the template. In the examples above:
        # {segment_name}_{Shot}.v{version}.{SEQ}.dpx : <ext> is '.dpx' 
        # {Shot}.v{version}.batch : <ext> is '.batch'
        # etc.
        #
        # example substitution:
        #
        # Toolkit: 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        #
        # Flame:   'sequences/<name>/<shot name>/editorial/plates/<segment name>_<shot name>.v<version>.<frame><ext>'
        #
        #
        shot_parent_entity_type = self.get_setting("shot_parent_entity_type")
        
        # get the export template defs for all our templates
        # the definition is a string on the form 
        # 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        template_defs = {}
        template_defs["plate_template"] = self.get_template("plate_template").definition
        template_defs["batch_template"] = self.get_template("batch_template").definition        
        template_defs["shot_clip_template"] = self.get_template("shot_clip_template").definition
        template_defs["segment_clip_template"] = self.get_template("segment_clip_template").definition
        
        # perform substitutions
        self.log_debug("Performing Toolkit -> Flame template field substitutions:")
        for t in template_defs:
            
            self.log_debug("Toolkit: %s" % template_defs[t])
            
            template_defs[t] = template_defs[t].replace("{%s}" % shot_parent_entity_type, "<name>")
            template_defs[t] = template_defs[t].replace("{Shot}", "<shot name>")
            template_defs[t] = template_defs[t].replace("{segment_name}", "<segment name>")
            template_defs[t] = template_defs[t].replace("{version}", "<version>")
            
            template_defs[t] = template_defs[t].replace("{SEQ}", "<frame>")
            
            template_defs[t] = template_defs[t].replace("{YYYY}", "<YYYY>")
            template_defs[t] = template_defs[t].replace("{MM}", "<MM>")
            template_defs[t] = template_defs[t].replace("{DD}", "<DD>")
            template_defs[t] = template_defs[t].replace("{hh}", "<hh>")
            template_defs[t] = template_defs[t].replace("{mm}", "<mm>")
            template_defs[t] = template_defs[t].replace("{ss}", "<ss>")
            template_defs[t] = template_defs[t].replace("{width}", "<width>")
            template_defs[t] = template_defs[t].replace("{height}", "<height>")
            
            # Now carry over the sequence token
            (head, ext) = os.path.splitext(template_defs[t])
            template_defs[t] = "%s<ext>" % head
            
            self.log_debug("Flame:  %s" % template_defs[t])
        
        return template_defs



    def pre_export_sequence(self, session_id, info):
        """
        Called from the flame hooks before export.
        This is the time to set up the structure in Shotgun.
        
        :param session_id: String which identifies which export session is being referred to

        :param info: Information about the export. Contains the keys      
                     - destinationHost: Host name where the exported files will be written to.
                     - destinationPath: Export path root.
                     - sequenceName: Name of the exported sequence.
                     - shotNames: Tuple of all shot names in the exported sequence. 
                                  Multiple segments could have the same shot name.
                     - abort: Hook can set this to True if the export sequence process should
                              be aborted. If other sequences are exported in the same export session
                              they will still be exported even if this export sequence is aborted.
                     - abortMessage: Error message to be displayed to the user when the export sequence
                                     process has been aborted.
        """
        sequence_name = info["sequenceName"]
        shot_names = info["shotNames"]
        
        if len(shot_names) == 0:
            from PySide import QtGui     
            QtGui.QMessageBox.warning(None,
                                      "Please name your shots!",
                                      "The Shotgun integration requires you to name your shots. Please go back to "
                                      "the time line and ensure that all clips have been given shot names before "
                                      "proceeding!")
            info["abort"] = True
            info["abortMessage"] = "Cannot export due to missing shot names."
            return
        
        self.log_debug("Preparing export structure for sequence %s and shots %s" % (sequence_name, shot_names))
        self.engine.show_busy("Preparing Shotgun...", "Preparing Shots for export...")
        
        try:
            # find and create objects in shotgun
            shot_metadata_list = self._sg_submit_helper.resolve_sg_shot_structure(sequence_name, shot_names)
            
            # set up metadata objects grouped by sequence in our self._shots structure
            self._shots[sequence_name] = {}
            
            for shot_metadata in shot_metadata_list:
                self._shots[sequence_name][shot_metadata.name] = shot_metadata
            
            # run folder creation for our newly created shots
            for shot_metadata in self._shots[sequence_name].values():
                #if data["created"]:
                # this is a new shot    
                self.engine.show_busy("Preparing Shotgun...", "Creating folders for Shot '%s'..." % shot_metadata.name)
                self.sgtk.create_filesystem_structure("Shot", shot_metadata.shotgun_id, engine="tk-flame")
            
            # establish a context for all objects
            self.engine.show_busy("Preparing Shotgun...", "Resolving Shot contexts...")
            for shot_metadata in self._shots[sequence_name].values():
                shot_metadata.context = self.sgtk.context_from_entity("Shot", shot_metadata.shotgun_id)
            
        finally:
            # kill progress indicator        
            self.engine.clear_busy()
    

    
    def pre_export_asset(self, session_id, info):
        """
        Called when an item is about to be exported and a path needs to be computed.
 
        :param session_id: String which identifies which export session is being referred to.
                           This parameter makes it possible to distinguish between different 
                           export sessions running if this is needed (typically only needed for
                           expert use cases).

        :param info: Dictionary with a number of parameters:
        
           destinationHost: Host name where the exported files will be written to.
           destinationPath: Export path root.
           namePattern:     List of optional naming tokens.
           resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
           assetName:       Name of the exported asset.
           sequenceName:    Name of the sequence the asset is part of.
           shotName:        Name of the shot the asset is part of.
           assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
           width:           Frame width of the exported asset.
           height:          Frame height of the exported asset.
           aspectRatio:     Frame aspect ratio of the exported asset.
           depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
           scanFormat:      Scan format of the exported asset. ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )
           fps:             Frame rate of exported asset.
           sequenceFps:     Frame rate of the sequence the asset is part of.
           sourceIn:        Source in point in frame and asset frame rate.
           sourceOut:       Source out point in frame and asset frame rate.
           recordIn:        Record in point in frame and sequence frame rate.
           recordOut:       Record out point in frame and sequence frame rate.
           track:           ID of the sequence's track that contains the asset.
           trackName:       Name of the sequence's track that contains the asset.
           segmentIndex:    Asset index (1 based) in the track.
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).        
        """
        
        asset_type = info["assetType"]
        asset_name = info["assetName"]
        shot_name = info["shotName"]
        sequence_name = info["sequenceName"]

        if asset_type not in ["video", "batch", "batchOpenClip", "openClip"]:
            # the review system ignores any other assets. The export profiles are defined
            # in the app's settings hook, so technically there shouldn't be any other items
            # generated - but just in case there are (because of customizations), we'll simply
            # ignore these.
            return
        
        # first check that the clip has a shot name - otherwise things won't work!
        if shot_name == "":
            from PySide import QtGui, QtCore
            QtGui.QMessageBox.warning(None,
                                      "Missing shot name!",
                                      ("The clip '%s' does not have a shot name and therefore cannot be exported. "
                                      "Please ensure that all shots you wish to exports "
                                      "have been named. " % asset_name) )
            
            # TODO: send the clip to the trash for now. no way to abort at this point
            # but we don't have enough information to be able to proceed at this point either
            info["resolvedPath"] = "flame_trash/unnamed_shot_%s" % uuid.uuid4().hex
            
            # TODO: can we avoid this export altogether?
            return
        
        # first, calculate cut data fields
        if asset_type == "video":
            self._shots[sequence_name][shot_name].update_new_cut_info(int(info["recordIn"]), int(info["recordOut"]))
                
        # get the appropriate file system template
        if asset_type == "video":
            # exported plates or video
            template = self.get_template("plate_template")
            
        elif asset_type == "batch":
            # batch file
            template = self.get_template("batch_template")
            
        elif asset_type == "batchOpenClip":
            # shot level open scene clip xml
            template = self.get_template("shot_clip_template")            

        elif asset_type == "openClip":
            # segment level open scene clip xml
            template = self.get_template("segment_clip_template")            
        
        self.log_debug("Attempting to resolve template %s..." % template)
        
        # resolve the template via the context
        context = self._shots[sequence_name][shot_name].context

        # resolve the fields out of the context
        self.log_debug("Resolving template %s using context %s" % (template, context))
        fields = context.as_template_fields(template)
        self.log_debug("Resolved context based fields: %s" % fields)
        
        if asset_type == "video":
            # handle the flame sequence token - it will come in as "[1001-1100]"
            re_match = re.search("(\[[0-9]+-[0-9]+\])\.", info["resolvedPath"])
            if not re_match:
                raise TankError("Cannot find frame number token in export data!")
            fields["SEQ"] = re_match.group(1)

        # create some fields based on the info in the info params                
        if "versionNumber" in info:
            fields["version"] = int(info["versionNumber"])
        
        fields["segment_name"] = asset_name
            
        if "width" in info:
            fields["width"] = int(info["width"])

        if "height" in info:
            fields["height"] = int(info["height"])
        
        # populate the time field metadata
        now = datetime.datetime.now()
        fields["YYYY"] = now.year
        fields["MM"] = now.month
        fields["DD"] = now.day
        fields["hh"] = now.hour
        fields["mm"] = now.minute
        fields["ss"] = now.second

        try:
            full_path = template.apply_fields(fields)
        except Exception, e:
            raise TankError("Could not resolve a file system path " 
                            "from template %s and fields %s: %s" % (template, fields, e))
        
        self.log_debug("Resolved %s -> %s" % (fields, full_path))
        
        # chop off the root of the path - the resolvedPath should be local to the destinationPath
        local_path = full_path[len(info["destinationPath"])+1:]
        
        self.log_debug("Chopping off root path %s -> %s" % (full_path, local_path))
        
        # pass an updated path back to the flame. This ensures that all the 
        # character substitutions etc are handled according to the toolkit logic 
        info["resolvedPath"] = local_path        
        
    def submit_post_asset_backburner_job(self, session_id, info):
        """
        Called when an item has been exported.
        
        :param session_id: String which identifies which export session is being referred to.
                           This parameter makes it possible to distinguish between different 
                           export sessions running if this is needed (typically only needed for
                           expert use cases).

        :param info: Dictionary with a number of parameters:
        
           destinationHost: Host name where the exported files will be written to.
           destinationPath: Export path root.
           namePattern:     List of optional naming tokens.
           resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
           name:            Name of the exported asset.
           sequenceName:    Name of the sequence the asset is part of.
           shotName:        Name of the shot the asset is part of.
           assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
           isBackground:    True if the export of the asset happened in the background.
           backgroundJobId: Id of the background job given by the backburner manager upon submission. 
                            Empty if job is done in foreground.
           width:           Frame width of the exported asset.
           height:          Frame height of the exported asset.
           aspectRatio:     Frame aspect ratio of the exported asset.
           depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
           scanFormat:      Scan format of the exported asset. ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )
           fps:             Frame rate of exported asset.
           sequenceFps:     Frame rate of the sequence the asset is part of.
           sourceIn:        Source in point in frame and asset frame rate.
           sourceOut:       Source out point in frame and asset frame rate.
           recordIn:        Record in point in frame and sequence frame rate.
           recordOut:       Record out point in frame and sequence frame rate.
           track:           ID of the sequence's track that contains the asset.
           trackName:       Name of the sequence's track that contains the asset.
           segmentIndex:    Asset index (1 based) in the track.       
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).

        """
        asset_type = info["assetType"] 
        asset_name = info["assetName"]
        shot_name = info["shotName"]
        sequence_name = info["sequenceName"]        
        
        if asset_type not in ["video", "batch"]:
            # the review system ignores any other assets. The export profiles are defined
            # in the app's settings hook, so technically there shouldn't be any other items
            # generated - but just in case there are (because of customizations), we'll simply
            # ignore these.
            return
        
        if info.get("isBackground"):
            run_after_job_id = info.get("backgroundJobId")
        else:
            run_after_job_id = None
        
        # extract context to pass downstream to the content generation job
        # note - we have cached the context object for performance - could have
        context = self._shots[sequence_name][shot_name].context
                
        # check if we should push a thumbnail to the shot entity
        # (this is typically done for newly created shots)
        # note: with upcoming changes in shotgun, this may not be necessary
        make_shot_thumb = False
        if asset_type == "video":
            make_shot_thumb = self._shots[sequence_name][shot_name].needs_shotgun_thumb()        
        
        # now start preparing a remote job
        args = {"info": info, 
                "serialized_context": sgtk.context.serialize(context),
                "user_comments": self._user_comments,
                "make_shot_thumb": make_shot_thumb }
        
        # and populate backburner job parameters
        job_title = "Shotgun Upload - %s, %s, %s" % (sequence_name, shot_name, asset_type)
        job_desc = "Transcoding media, registering and uploading."         
        
        # kick off backburner job
        self.engine.create_local_backburner_job(job_title, 
                                                job_desc, 
                                                run_after_job_id, 
                                                self, 
                                                "backburner_process_exported_asset", 
                                                args)
        
        # all done - the rest will happen on the render farm.
        self._submission_done = True


    def __is_rendering_tk_session(self, batch_path, render_path):
        """
        Determines if a batch export is outputting to file locations
        known to the current tk export app. In that case, the context
        is returned.
        
        :param batch_path: Path to the exported batch file
        :param render_path: Path to the current render (w flame sequence markers)
        :returns: Context or None if path isn't recognized 
        """
        
        # first check if the resolved paths match our templates in the settings.
        # otherwise ignore the export
        plate_template = self.get_template("plate_template")
        if not plate_template.validate(render_path):
            self.log_debug("The path '%s' does not match the template '%s'. Ignoring." % (render_path, plate_template))
            return None
        
        batch_template = self.get_template("batch_template")
        if not batch_template.validate(batch_path):
            self.log_debug("The path '%s' does not match the template '%s'. Ignoring." % (batch_path, batch_template))
            return None

        # now extract the context for the currently worked on thing
        context = self.sgtk.context_from_path(batch_path)
        return context


    def pre_batch_render_checks(self, info):
        """
        Called before rendering starts in batch/flare.
        
        This pops up a UI asking the user if they want to send things to review.
        
        :param info: Dictionary with a number of parameters:
        
            nodeName:             Name of the export node.   
            exportPath:           Export path as entered in the application UI.
                                  Can be modified by the hook to change where the file are written.
            namePattern:          List of optional naming tokens as entered in the application UI.
            resolvedPath:         Full file pattern that will be exported with all the tokens resolved.
            firstFrame:           Frame number of the first frame that will be exported.
            lastFrame:            Frame number of the last frame that will be exported.
            versionName:          Current version name of export (Empty if unversioned).
            versionNumber:        Current version number of export (0 if unversioned).
            openClipNamePattern:  List of optional naming tokens pointing to the open clip created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            openClipResolvedPath: Full path to the open clip created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            setupNamePattern:     List of optional naming tokens pointing to the setup created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            setupResolvedPath:    Full path to the setup created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            aborted:              Indicate if the export has been aborted by the user.
            lastFrame:            Last frame rendered
            firstFrame:           First frame rendered
            fps:                  Frame rate of render
            aspectRatio:          Frame aspect ratio
            width:                Frame width
            height:               Frame height
            depth:                Frame depth ( '8-bits', '10-bits', '12-bits', '16 fp' )
            scanForamt:           Scan format ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )        
        """
        self._send_batch_render_to_review = False
        self._user_comments = None
        
        plate_path = os.path.join(info.get("exportPath"), info.get("resolvedPath"))
        batch_path = info.get("setupResolvedPath")
        ctx = self.__is_rendering_tk_session(batch_path, plate_path)
        if ctx is None:
            # not known by this app
            return
        
        # ok so this looks like one of our renders - check with the user 
        # if they want to submit to review!
        from PySide import QtGui, QtCore
         
        # pop up a UI asking the user for description
        tk_flame_export = self.import_module("tk_flame_export")        
        (return_code, widget) = self.engine.show_modal("Send to Review", self, tk_flame_export.BatchRenderDialog)
        
        if return_code != QtGui.QDialog.Rejected:
            # user wants review!
            self._send_batch_render_to_review = True
            self._user_comments = widget.get_comments()


    def submit_post_batch_backburner_job(self, info):
        """
        Called when batch rendering has finished.
        
        :param info: Dictionary with a number of parameters:
        
            nodeName:             Name of the export node.   
            exportPath:           Export path as entered in the application UI.
                                  Can be modified by the hook to change where the file are written.
            namePattern:          List of optional naming tokens as entered in the application UI.
            resolvedPath:         Full file pattern that will be exported with all the tokens resolved.
            firstFrame:           Frame number of the first frame that will be exported.
            lastFrame:            Frame number of the last frame that will be exported.
            versionName:          Current version name of export (Empty if unversioned).
            versionNumber:        Current version number of export (0 if unversioned).
            openClipNamePattern:  List of optional naming tokens pointing to the open clip created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            openClipResolvedPath: Full path to the open clip created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            setupNamePattern:     List of optional naming tokens pointing to the setup created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            setupResolvedPath:    Full path to the setup created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            aborted:              Indicate if the export has been aborted by the user.
            lastFrame:            Last frame rendered
            firstFrame:           First frame rendered
            fps:                  Frame rate of render
            aspectRatio:          Frame aspect ratio
            width:                Frame width
            height:               Frame height
            depth:                Frame depth ( '8-bits', '10-bits', '12-bits', '16 fp' )
            scanFormat:           Scan format ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )
            aborted:              Indicate if the export has been aborted by the user.
        """
        
        if "aborted" in info and info["aborted"]:
            self.log_debug("Rendering was aborted. Will not push to Shotgun.")
            return 
        
        plate_path = os.path.join(info.get("exportPath"), info.get("resolvedPath"))
        batch_path = info.get("setupResolvedPath")
        ctx = self.__is_rendering_tk_session(batch_path, plate_path)
        if ctx is None:
            # not known by this app
            return
        
        # now start preparing a remote job
        args = {"info": info, 
                "serialized_context": sgtk.context.serialize(ctx), 
                "comments": self._user_comments,
                "send_to_review": self._send_batch_render_to_review }
        
        # and populate backburner job parameters
        job_title = "Shotgun Batch Render Upload - %s" % info.get("nodeName")
        job_desc = "Making quicktimes and uploading to Shotgun."
        
        # kick off async job
        self.engine.create_local_backburner_job(job_title, 
                                                job_desc, 
                                                None, # run_after_job_id 
                                                self, 
                                                "backburner_process_rendered_batch", 
                                                args)

    def backburner_process_rendered_batch(self, info, serialized_context, comments, send_to_review):
        """
        :param info: Dictionary with a number of parameters:
        
            nodeName:             Name of the export node.   
            exportPath:           Export path as entered in the application UI.
                                  Can be modified by the hook to change where the file are written.
            namePattern:          List of optional naming tokens as entered in the application UI.
            resolvedPath:         Full file pattern that will be exported with all the tokens resolved.
            firstFrame:           Frame number of the first frame that will be exported.
            lastFrame:            Frame number of the last frame that will be exported.
            versionName:          Current version name of export (Empty if unversioned).
            versionNumber:        Current version number of export (0 if unversioned).
            openClipNamePattern:  List of optional naming tokens pointing to the open clip created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            openClipResolvedPath: Full path to the open clip created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            setupNamePattern:     List of optional naming tokens pointing to the setup created if any
                                  as entered in the application UI. This is only available if versioning
                                  is enabled.
            setupResolvedPath:    Full path to the setup created if any with all the tokens resolved.
                                  This is only available if versioning is enabled.
            aborted:              Indicate if the export has been aborted by the user.
            lastFrame:            Last frame rendered
            firstFrame:           First frame rendered
            fps:                  Frame rate of render
            aspectRatio:          Frame aspect ratio
            width:                Frame width
            height:               Frame height
            depth:                Frame depth ( '8-bits', '10-bits', '12-bits', '16 fp' )
            scanForamt:           Scan format ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' ) 
            
        :param serialized_context: The context for the shot that the submission 
                                   is associated with, in serialized form.
        :param comments: User comments, as a string
        :param send_to_review: Boolean to indicate that we should send to sg review.            
        """
        context = sgtk.context.deserialize(serialized_context)
        version_number = int(info["versionNumber"])
        description = comments or "Automatic Flame batch render"
        
        
        # first register the batch file as a publish in Shotgun
        batch_path = info.get("setupResolvedPath")
        self._sg_submit_helper.register_batch_publish(context, batch_path, description, version_number)

        # Now register the rendered images as a published plate in Shotgun
        full_flame_plate_path = os.path.join(info.get("exportPath"), info.get("resolvedPath"))
        sg_data = self._sg_submit_helper.register_video_publish(context, 
                                                                full_flame_plate_path, 
                                                                description,
                                                                version_number, 
                                                                info["width"], 
                                                                info["height"], 
                                                                make_shot_thumb=False)
        
        # Finally, create a version record in Shotgun, generate a quicktime and upload it
        if send_to_review:
            self._sg_submit_helper.create_version(context, 
                                                  full_flame_plate_path,
                                                  description,
                                                  sg_data, 
                                                  info["width"], 
                                                  info["height"],
                                                  info["aspectRatio"])        


    def backburner_process_exported_asset(self, info, serialized_context, user_comments, make_shot_thumb):
        """
        Called when an item has been exported
        
        :param info: Dictionary with a number of parameters:
        
           destinationHost: Host name where the exported files will be written to.
           destinationPath: Export path root.
           namePattern:     List of optional naming tokens.
           resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
           assetName:            Name of the exported asset.
           sequenceName:    Name of the sequence the asset is part of.
           shotName:        Name of the shot the asset is part of.
           assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
           isBackground:    True if the export of the asset happened in the background.
           backgroundJobId: Id of the background job given by the backburner manager upon submission. 
                            Empty if job is done in foreground.
           width:           Frame width of the exported asset.
           height:          Frame height of the exported asset.
           aspectRatio:     Frame aspect ratio of the exported asset.
           depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
           scanFormat:      Scan format of the exported asset. ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )
           fps:             Frame rate of exported asset.
           sequenceFps:     Frame rate of the sequence the asset is part of.
           sourceIn:        Source in point in frame and asset frame rate.
           sourceOut:       Source out point in frame and asset frame rate.
           recordIn:        Record in point in frame and sequence frame rate.
           recordOut:       Record out point in frame and sequence frame rate.
           track:           ID of the sequence's track that contains the asset.
           trackName:       Name of the sequence's track that contains the asset.
           segmentIndex:    Asset index (1 based) in the track.       
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).
           
        :param serialized_context: The context for the shot that the submission is associated with, in serialized form.
        :param user_comments: Comments entered by the user at export start.
        :param make_shot_thumb: Should a thumbnail be uploaded to the associated shot as well?
        """
        
        path = os.path.join(info.get("destinationPath"), info.get("resolvedPath"))
        context = sgtk.context.deserialize(serialized_context)
        version_number = int(info["versionNumber"])
        
        if info.get("assetType") == "video":
            
            # first register a publish record in Shotgun for the plates
            sg_data = self._sg_submit_helper.register_video_publish(context,
                                                                    path,
                                                                    user_comments,
                                                                    version_number,
                                                                    info["width"],
                                                                    info["height"],
                                                                    make_shot_thumb)

            # now create a version record, generate a quicktime and upload it            
            self._sg_submit_helper.create_version(context,
                                                  path,
                                                  user_comments,
                                                  sg_data,
                                                  info["width"],
                                                  info["height"],
                                                  info["aspectRatio"])
            
        elif info.get("assetType") == "batch":
            
            # register a publish record in Shotgun for the batch file
            self._sg_submit_helper.register_batch_publish(context, path, user_comments, version_number)
                        
        else:
            raise TankError("Unsupported asset type '%s'" % info.get("assetType"))
        
                        
    def update_cut_and_display_summary(self, session_id, info):
        """
        Show summary UI to user
        
        :param session_id: String which identifies which export session is being referred to.
                           This parameter makes it possible to distinguish between different 
                           export sessions running if this is needed (typically only needed for
                           expert use cases).
        
        :param info: Information about the export. Contains the keys      
                     - destinationHost: Host name where the exported files will be written to.
                     - destinationPath: Export path root.
                     - presetPath: Path to the preset used for the export.
        
        """        
        
        # calculate the cut order for each sequence
        for seq in self._shots:
            # get a list of metadata objects for this shot
            shot_metadata = self._shots[seq].values()
            # sort it by cut in
            shot_metadata.sort(key=lambda x: x.new_cut_in)
            # now loop over all items and set an incrementing cut order
            cut_index = 1
            for sm in shot_metadata:
                sm.new_cut_order = cut_index
                cut_index += 1
                
        # now push cut changes to Shotgun as a single batch op
        cut_changes = []
        for seq in self._shots:
            for sm in self._shots[seq].values():
                
                if sm.shotgun_cut_in != sm.new_cut_in or \
                   sm.shotgun_cut_out != sm.new_cut_out or \
                   sm.shotgun_cut_order != sm.new_cut_order:
                    
                    duration = sm.new_cut_out - sm.new_cut_in + 1
                    
                    cut_changes.append( {"request_type":"update", 
                                         "entity_type": "Shot",
                                         "entity_id": sm.shotgun_id,
                                         "data":{ "sg_cut_in": sm.new_cut_in,
                                                  "sg_cut_out": sm.new_cut_out,
                                                  "sg_cut_duration": duration, 
                                                  "sg_cut_order": sm.new_cut_order }} )


        self.log_debug("Sending cut order changes to Shotgun: %s" % cut_changes)
        if len(cut_changes) > 0:
            self.shotgun.batch(cut_changes)
                

        # pop up a UI asking the user for description
        tk_flame_export = self.import_module("tk_flame_export")
        self.engine.show_modal("Submission Summary", self, tk_flame_export.SummaryDialog, self._submission_done)
        
        
        
