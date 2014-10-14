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
import copy
import uuid
import os
import re
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
        
        # shot metadata
        self._shots = {}
        
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
        callbacks["postExportAsset"] = self.register_post_asset_job
        callbacks["postCustomExport"] = self.update_cut_and_display_summary
        
        # register with the engine
        self.engine.register_export_hook(menu_caption, callbacks)


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
            info["destinationHost"] = "localhost"
            # let the export root path align with the primary project root
            info["destinationPath"] = self.sgtk.project_path
            # pick up the xml export profile from the configuration
            flame_templates = self.__resolve_flame_templates()
            info["presetPath"] = self.execute_hook_method("settings_hook", 
                                                          "get_export_preset",
                                                          resolved_flame_templates=flame_templates)
            self.log_debug("%s: Starting custom export session with preset '%s'" % (self, info["presetPath"]))
        

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
            shot_metadata_list = self.__resolve_sg_shot_structure(sequence_name, shot_names)
            
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
    
    def __resolve_sg_shot_structure(self, parent_name, shot_names):
        """
        Ensures that Shots exists in Shotgun. Will automatically create
        Shots and Shot parents (e.g. sequences) if necessary and assign
        task templates. Returns a dictionary with Shot metadata
        
        :returns: List of ShotMetadata objects  
        """
        # get some configuration settings first
        shot_task_template = self.get_setting("task_template")
        if shot_task_template == "":
            shot_task_template = None

        parent_task_template = self.get_setting("shot_parent_task_template")
        if parent_task_template == "":
            parent_task_template = None

        shot_parent_entity_type = self.get_setting("shot_parent_entity_type")
        shot_parent_link_field = self.get_setting("shot_parent_link_field")

        # handy shorthand
        project = self.context.project

        # first, ensure that a parent exists in Shotgun with the parent name
        sg_parent = self.shotgun.find_one(shot_parent_entity_type, [["code", "is", parent_name], 
                                                                    ["project", "is", project]]) 
        
        if not sg_parent:
            # Create a new parent object in Shotgun
            
            # First see if we should assign a task template
            if parent_task_template:
                # resolve task template
                sg_task_template = self.shotgun.find_one("TaskTemplate", [["code", "is", parent_task_template]])
                if not sg_task_template:
                    raise TankError("The task template '%s' does not exist in Shotgun!" % parent_task_template)
            else:
                sg_task_template = None
            
            sg_parent = self.shotgun.create(shot_parent_entity_type, 
                                            {"code": parent_name, 
                                             "task_template": sg_task_template,
                                             "description": "Created by the Shotgun Flame exporter.",
                                             "project": project})
  
        # now resolve all the shots. Shots that don't already exists are created.
        shots = []
        for shot_name in shot_names:

            shot = self.shotgun.find_one("Shot", 
                                         [["code", "is", shot_name], [shot_parent_link_field, "is", sg_parent]],
                                         ["sg_cut_in", "sg_cut_out", "sg_cut_order"])
            
            metadata = ShotMetadata()
            metadata.name = shot_name
            metadata.parent_name = parent_name
            metadata.shotgun_parent = sg_parent
            shots.append(metadata)
            
            if shot:
                # store it in our return data dict
                metadata.shotgun_id = shot["id"]
                metadata.shotgun_cut_in = shot["sg_cut_in"]
                metadata.shotgun_cut_out = shot["sg_cut_out"]
            
            else:
                # Create a new shot in Shotgun
                
                # First see if we should assign a task template
                if shot_task_template:
                    # resolve task template
                    sg_task_template = self.shotgun.find_one("TaskTemplate", [["code", "is", shot_task_template]])
                    if not sg_task_template:
                        raise TankError("The task template '%s' does not exist in Shotgun!" % shot_task_template)
                else:
                    sg_task_template = None
                    
                shot = self.shotgun.create("Shot", {"code": shot_name, 
                                                    "description": "Created by the Shotgun Flame exporter.",
                                                    shot_parent_link_field: sg_parent,
                                                    "task_template": sg_task_template,
                                                    "project": project})
                
                # store it in our return data dict
                metadata.created_this_session = True
                metadata.shotgun_id = shot["id"]
            
        return shots

    
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
            # get the cut in and out point for this clip
            clip_in = int(info["sourceIn"])
            clip_out = int(info["sourceOut"])
            
            if self._shots[sequence_name][shot_name].new_cut_in is None:
                # no value yet
                self._shots[sequence_name][shot_name].new_cut_in = clip_in
            
            elif self._shots[sequence_name][shot_name].new_cut_in > clip_in:
                # we got a value but our current clip started before
                # the other. We want to capture the maximum range of 
                # the shot, so update
                self._shots[sequence_name][shot_name].new_cut_in = clip_in
                
            if self._shots[sequence_name][shot_name].new_cut_out is None:
                # no value yet
                self._shots[sequence_name][shot_name].new_cut_out = clip_out
                
            elif self._shots[sequence_name][shot_name].new_cut_out < clip_out:
                # we got a value but our current clip ended after
                # the other. We want to capture the maximum range of 
                # the shot, so update
                self._shots[sequence_name][shot_name].new_cut_out = clip_out
                
        # get the appropriate file system template
        if asset_type == "video":
            template = self.get_template("plate_template")
            
        elif asset_type == "batch":
            template = self.get_template("batch_template")
            
        elif asset_type == "batchOpenClip":
            template = self.get_template("shot_clip_template")            

        elif asset_type == "openClip":
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
            re_match = re.search('(\[[0-9]+-[0-9]+\])\.', info["resolvedPath"])
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

        # the template and fields are needed in the post-asset export, so add them 
        # to our data structure that we are passing down the pipe. 
        self._shots[sequence_name][shot_name].set_template(asset_type, asset_name, template, fields)
        
        
    def register_post_asset_job(self, session_id, info):
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
        context = self._shots[sequence_name][shot_name].context
        
        # get a shotgun-friendly path where the sequence identifier is %xd 
        toolkit_path = self._shots[sequence_name][shot_name].get_std_sequence_path(asset_type, asset_name)        
        
        # check if we should push a thumbnail to the shot
        make_shot_thumb = False
        if asset_type == "video":
            make_shot_thumb = self._shots[sequence_name][shot_name].needs_shotgun_thumb()        
        
        # now start preparing a remote job
        args = {"info": info, 
                "serialized_shot_context": sgtk.context.serialize(context),
                "toolkit_path": toolkit_path,
                "user_comments": self._user_comments,
                "make_shot_thumb": make_shot_thumb }
        
        # and populate backburner job parameters
        backburner_job_title = "Shotgun Upload - %s, %s, %s" % (sequence_name, shot_name, asset_type)
        backburner_job_desc = "Transcoding media, registering and uploading."         
        
        # kick off async job
        self.engine.create_local_backburner_job(backburner_job_title, 
                                                backburner_job_desc, 
                                                run_after_job_id,
                                                self, 
                                                "populate_shotgun",
                                                args)
        
        # all done - the rest will happen on the render farm.
        self._submission_done = True

    def populate_shotgun(self, info, serialized_shot_context, toolkit_path, user_comments, make_shot_thumb):
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
           
        :param serialized_shot_context: The context for the shot that the submission is associated with, 
                                        in serialized form.
        :param toolkit_path: Path to the file or sequence, toolkit style
        :param user_comments: Comments entered by the user at export start.
        :param make_shot_thumb: Should a thumbnail be uploaded to the associated shot as well?
        """

        self.log_debug("Creating publish in Shotgun...")
                
        shot_context = sgtk.context.deserialize(serialized_shot_context)
        
        if info.get("assetType") == "video":
            publish_type = self.get_setting("plate_publish_type")
            
        elif info.get("assetType") == "batch":
            publish_type = self.get_setting("batch_publish_type")
                        
        else:
            raise TankError("Unsupported asset type '%s'" % info.get("assetType"))
        
        # join together the full path, flame style        
        full_flame_path = os.path.join(info.get("destinationPath"), info.get("resolvedPath"))
                        
        # put together a name for the publish. This should be on a form without a version
        # number, so that it can be used to group together publishes of the same kind, but
        # with different versions. The logic will differ depending on asset type
        
        if info["assetType"] == "video":
            # e.g. 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
            publish_name = "%s, %s, %s" % (info["sequenceName"], info["shotName"], info["assetName"])
            
        elif info["assetType"] == "batch":
            # e.g. 'sequences/{Sequence}/{Shot}/editorial/flame/batch/{Shot}.v{version}.batch'
            publish_name = "%s, %s" % (info["sequenceName"], info["shotName"])
            
        else:
            raise TankError("Unknown asset type %s" % info["assetType"])
        
        # now start assemble publish parameters
        args = {
            "tk": self.sgtk,
            "context": shot_context,
            "comment": user_comments,
            "path": toolkit_path,
            "name": publish_name,
            "version_number": int(info["versionNumber"]),
            "created_by": shot_context.user,
            "task": shot_context.task,
            "published_file_type": publish_type,
        }
        
        thumbnail_jpg = None
        
        if info.get("assetType") == "video":
            # now try to extract a thumbnail from the asset data stream.
            # we use the same mechanism that the quicktime generation is using - see
            # the quicktime code below for details:
            #    
            input_cmd = "%s -n \"%s@CLIP\" -h %s -W %s -H %s -L" % (self.engine.get_read_frame_path(),
                                                                    full_flame_path,
                                                                    "localhost:Gateway",
                                                                    info["width"],
                                                                    info["height"])
            
            thumbnail_jpg = os.path.join(self.engine.get_backburner_tmp(), "tk_thumb_%s.jpg" % uuid.uuid4().hex)
            if os.system("%s > %s" % (input_cmd, thumbnail_jpg)) != 0:
                self.log_warning("Could not extract thumbnail! See error log for details.")
            else:
                self.log_debug("Wrote thumbnail %s" % thumbnail_jpg)
                # add the thumbnail to the publish generation
                args["thumbnail_path"] = thumbnail_jpg
            
            # check if the shot needs a thumbnail
            if make_shot_thumb:
                args["update_entity_thumbnail"] = True
        

        self.log_debug("Register publish in shotgun: %s" % str(args))        
        sg_publish_data = sgtk.util.register_publish(**args)
        self.log_debug("Register complete: %s" % sg_publish_data)
        
        if thumbnail_jpg:
            # try to clean up
            self.__clean_up_temp_file(thumbnail_jpg)
                    
        if info.get("assetType") == "video":
            self._create_version(info, shot_context, toolkit_path, sg_publish_data, user_comments)
            
    def _create_version(self, info, context, full_std_path, sg_publish_data, user_comments):
        """
        Process review portion of an export. 
        
        For video assets, this method will do the following:
        - Create a Shotgun version entity and populate as much metadata as possible
        - Generate a quicktime by streaming the asset data via wiretap into ffmepg.
          A h264 quicktime with shotgun-friendly settings are created, however the quicktime
          defaults are defined in the settings hook and can be controlled by the user.
        - Lastly, uploads the quicktime to Shotgun and then deletes it off disk.
        
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
           
        :param context: The context for the shot that the submission is associated with, 
                        in serialized form.
        :param full_std_path: Path to frames, using %04d rather than flame style [1234,1235] notation
        :param sg_publish_data: Std shotgun dictionary (with type and id), representing the publish
                                in Shotgun that has been carried out for this asset.
        :param user_comments: Comments entered by the user at export start.
        """
        
        # get the full flame style path
        full_flame_path = os.path.join(info["destinationPath"], info["resolvedPath"])
        
        # note / todo: there doesn't seem to be any way to downscale the quicktime
        # as it is being generated/streamed out of wiretap and encoded by ffmpeg.
        # ideally we would like to downrez it to height 720px prior to uploading
        # according to the Shotgun transcoding guidelines (and to optimize bandwidth)        
        width = info["width"]
        height = info["height"]

        self.log_debug("Begin version processing for %s..." % full_flame_path)

        data = {}
        data["code"] = publish_name = os.path.basename(full_std_path)
        data["description"] = user_comments
        data["project"] = context.project
        data["entity"] = context.entity
        data["created_by"] = context.user
        data["user"] = context.user
        data["sg_task"] = context.task

        # link to the publish
        if sgtk.util.get_published_file_entity_type(self.sgtk) == "PublishedFile":
            # client is using published file entity
            data["published_files"] = [sg_publish_data]
        else:
            # client is using old "TankPublishedFile" entity
            data["tank_published_file"] = sg_publish_data
        
        # populate the path to frames with a path which is using %4d syntax
        data["sg_path_to_frames"] = full_std_path

        # note: we don't have a quicktime on disk which we link up to.
        # we just upload it to shotgun and the discard it
        # data["sg_path_to_movie"] = None

        data["sg_first_frame"] = info["sourceIn"]
        data["sg_last_frame"] = info["sourceOut"]
        data["frame_count"] = info["sourceOut"] - info["sourceIn"] + 1 
        data["frame_range"] = "%s-%s" % (info["sourceIn"], info["sourceOut"])         
        data["sg_frames_have_slate"] = False
        data["sg_movie_has_slate"] = False         
        data["sg_frames_aspect_ratio"] = info["aspectRatio"]
        data["sg_movie_aspect_ratio"] = info["aspectRatio"]
        
        # This is used to find the latest Version from the same department.
        # todo: make this configurable?
        data["sg_department"] = "Editorial"        
        
        sg_version_data = self.shotgun.create("Version", data)
        
        self.log_debug("Created a version in Shotgun: %s" % sg_version_data)
        
        self.log_debug("Start transcoding quicktime...")

        # first assemble the readframe syntax. This will use the wiretap API to emit a stream of 
        # image data to stdout that we can pipe into ffmpeg. We use this because the ffmpeg version
        # coming with flame is from 2009 and doesn't support dpx files but also to make sure that
        # all file formats that flame supports (e.g. exrs) can be converted.
        # 
        # Syntax:
        #
        # Usage: ./read_frame
        #   -n <clip node id> (if empty, generate 4x4 black media)
        #   [ -h <Wiretap server ID> (default = localhost) ]
        #   [ -W <display width> (default=same as source) ]
        #   [ -H <display height> (default=same as source) ]
        #   [ -b <output bits per pixel (24|32)> (default = 24) ]
        #   [ -i <zero-based start frame idx> (default = 0) ]
        #   [ -N <number of frames to output> (default = 1, -1 for all)
        #   [ -r (output raw RGB, default=jpg) ]
        #   [ -O (flip raw output orientation, default=bottom to top) ]
        #   [ -L (use lowest resolution available, default=highest) ]
        #   [ -c <compression factor [0,100]> (default = 100)
        #   [ -p <processing options> (default = none)
        #
        # Command line example:
        # 
        # ./read_frame 
        #  -n /path/to.dpx@CLIP   <-- append @CLIP at the end of the path 
        #  -h localhost:Gateway   <-- connect to wiretap
        #  -W 1280 -H 720         <-- width and height to output
        #  -L                     <-- default to lowest resolution
        #  -N -1                  <-- output all frames 
        #  -r                     <-- output raw rgb stream
        # 
        input_cmd = "%s -n \"%s@CLIP\" -h %s -W %s -H %s -L -N -1 -r" % (self.engine.get_read_frame_path(),
                                                                         full_flame_path,
                                                                         "localhost:Gateway",
                                                                         width,
                                                                         height)

        # we now pipe this image stream into ffmpeg and generate a quicktime
        #
        # example command line:
        # 
        # ./ffmpeg -f rawvideo -top -1 -pix_fmt rgb24 -s 1280x720 -i -  -y -r 25 QUICKTIME_OPTIONS /output/file.mov
        #
        # ./ffmpeg 
        #  -f rawvideo         <-- tell ffmpeg to read a raw stream from stdin
        #  -top -1             <-- automatically interpret the stream data flow direction
        #  -pix_fmt rgb24      <-- input stream pixel data lay out
        #  -s 1280x720         <-- input stream resolution
        #  -i -                <-- no input file
        #  -y                  <-- overwrite existing files
        #  -r 25               <-- need to tell ffmpeg what the fps is 
        #  QUICKTIME_OPTIONS   <-- quicktime codec options (comes from hook)
        #  /output/file.mov    <-- target file
        #
        
        # note: the -r framerate argument seems to confuse ffmpeg so I am omitting that
        # instead, quicktimes are generated at 25fps.
        
        ffmpeg_cmd = "%s -f rawvideo -top -1 -pix_fmt rgb24 -s %sx%s -i - -y" % (self.engine.get_ffmpeg_path(),
                                                                                 width,
                                                                                 height)
                                                                                       
        # get quicktime settings
        ffmpeg_presets = self.execute_hook_method("settings_hook", "get_ffmpeg_quicktime_encode_parameters")
        # generate target file
        tmp_quicktime = os.path.join(self.engine.get_backburner_tmp(), "tk_flame_%s.mov" % uuid.uuid4().hex) 

        full_cmd = "%s | %s %s %s" % (input_cmd, ffmpeg_cmd, ffmpeg_presets, tmp_quicktime)
        
        self.log_debug("Transcoding command line: %s" % full_cmd)
        
        if os.system(full_cmd) != 0:
            raise TankError("Could not transcode media. See error log for details.")
        
        self.log_debug("Quicktime successfully created!")
        self.log_debug("File size is %s bytes." % os.path.getsize(tmp_quicktime))
        
        # upload quicktime to Shotgun
        self.log_debug("Begin upload of quicktime to shotgun...")
        self.shotgun.upload("Version", sg_version_data["id"], tmp_quicktime, "sg_uploaded_movie")
        self.log_debug("Upload complete!")
        
        # clean up
        self.__clean_up_temp_file(tmp_quicktime)
    

    def __clean_up_temp_file(self, path):
        """
        Helper method which attemps to delete up a given temp file.
        
        :param path: Path to delete
        """
        try:
            os.remove(path)
            self.log_debug("Removed temporary file '%s'." % path)
        except Exception, e:
            self.log_warning("Could not remove temporary file '%s': %s" % (path, e))    
    
        
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
                
                if sm.shotgun_cut_in != sm.new_cut_in or sm.shotgun_cut_out != sm.new_cut_out or \
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
        
        
        
        
class ShotMetadata(object):
    """
    Value wrapper class which holds various properties associated with a shot.
    This object is passed down the export pipeline.
    """

    def __init__(self):
        """
        Constructor
        """
        # set up the basic properties of this value wrapper
        
        self.name = None                    # shot name
        self.parent_name = None             # parent (sequence) name
        self.shotgun_parent = None          # shotgun parent entity dictionary
        
        self.created_this_session = False   # was the shotgun shot created in this session?

        self.shotgun_id = None              # shotgun shot id
        
        self.shotgun_cut_in = None          # shotgun cut in 
        self.shotgun_cut_out = None         # shotgun cut out
        self.shotgun_cut_order = None       # shotgun cut order
        
        self.new_cut_in = None              # calculated cut in
        self.new_cut_out = None             # calculated cut out
        self.new_cut_order = None           # calculated cut order
        
        self.context = None                 # context object for the shot
        
        # internal members
        self.__templates = {}           
        self.__thumb_upload_handled = False
        
    def set_template(self, asset_type, asset_name, template, fields):
        """
        Associate a template and some fields with a given asset belonging to this shot. 
        
        :param asset_type: flame asset type to associate with
        :param asset_name: flame asset name to associate with 
        :param template: template object to store
        :param fields: fields dictionary (matching template) to store
        """
        self.__templates["%s_%s" % (asset_type, asset_name)] = (template, fields)

    def get_std_sequence_path(self, asset_type, asset_name):
        """
        Used in conjunction with set_template().
        
        Given an asset type and an asset name,
        resolve the associated template and fields into a path
        and return the path. Paths with sequence markers {SEQ}
        will be normalized on a %d-style sequence form.

        :param asset_type: flame asset type to associate with
        :param asset_name: flame asset name to associate with 
        :returns: resolved template, e.g. a path
        """
        
        # given the template and fields we calculated in the pre-asset hook,
        # compute a shotgun-friendly path where the sequence identifier has 
        # been turned into a %04d-equivalent:
        
        lookup = "%s_%s" % (asset_type, asset_name)
        if lookup not in self.__templates:
            raise TankError("Could not look up sequence path in metadata %s" % self)
        (template, fields) =  self.__templates[lookup]
        new_fields = copy.deepcopy(fields)
        new_fields["SEQ"] = "FORMAT: %d"
        return template.apply_fields(new_fields)        
        
    def needs_shotgun_thumb(self):
        """
        Returns true if it needs a shotgun thumbnail uploaded.
        
        For existing shotgun shots, this method will always return False.
        For new shotgun shots, this method will return True the first time
        it is being called and False after that.
        
        :returns: Boolean to indicate if a thumbnail is needed
        """
        if self.created_this_session == False:
            # no need for old items
            return False
        
        if self.__thumb_upload_handled:
            # some 
            return False
        
        # we handle the upload
        self.__thumb_upload_handled = True
        return True
    
    
