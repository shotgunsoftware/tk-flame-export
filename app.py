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
        callbacks["preExportSequence"] = self.prepare_export_structure
        callbacks["preExportAsset"] = self.adjust_path
        callbacks["postExportAsset"] = self.register_post_asset_job
        callbacks["postCustomExport"] = self.display_summary
        
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
        submit_dialog = self.import_module("submit_dialog")        
        (return_code, widget) = self.engine.show_modal("Submit to Shotgun", self, submit_dialog.Dialog)
        
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
            shot_parent_entity_type = self.get_setting("shot_parent_entity_type")
            info["presetPath"] = self.execute_hook_method("settings_hook", 
                                                          "get_export_preset",
                                                          shot_parent_template_field=shot_parent_entity_type)
            self.log_debug("%s: Starting custom export session with preset '%s'" % (self, info["presetPath"]))
        




    def prepare_export_structure(self, session_id, info):
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
            shots = self.__resolve_sg_shot_structure(sequence_name, shot_names)
            
            # shots will be on the form
            # {"aaa_xxxx": {"created": True, "shotgun": {"type": "Shot", "id": 123}, ...}
            
            # run folder creation for our newly created shots
            for (shot_name, data) in shots.iteritems():
                #if data["created"]:
                # this is a new shot    
                self.engine.show_busy("Preparing Shotgun...", "Creating folders for Shot '%s'..." % shot_name)
                self.sgtk.create_filesystem_structure("Shot", data["shotgun"]["id"], engine="tk-flame")
            
            # lastly, establish a context for all objects
            self.engine.show_busy("Preparing Shotgun...", "Resolving Shot contexts...")
            for shot_name in shots:
                sg_shot_id = shots[shot_name]["shotgun"]["id"]
                shots[shot_name]["context"] = self.sgtk.context_from_entity("Shot", sg_shot_id) 
        
            # and finally store the data for downstream consumption
            self._shots = shots 

        finally:
            # kill progress indicator        
            self.engine.clear_busy()
    
    def __resolve_sg_shot_structure(self, parent_name, shot_names):
        """
        Resolve Shotgun Shot structure given export data from Flame.
        
        This default implementation assumes that the parent is a Sequence.
        
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
        shots = {}
        for shot_name in shot_names:

            shot = self.shotgun.find_one("Shot", [["code", "is", shot_name], 
                                                  [shot_parent_link_field, "is", sg_parent]])
            if shot:
                # store it in our return data dict
                shots[shot_name] = {"created": False, "shotgun": shot}
            
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
                
                shots[shot_name] = {"created": True, "shotgun": shot} 
            
        return shots

    
    
    
    
    def adjust_path(self, session_id, info):
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
        
        # important notes!
        # 

        if info.get("assetType") not in ["video", "batch", "batchOpenClip", "openClip"]:
            # the review system ignores any other assets. The export profiles are defined
            # in the app's settings hook, so technically there shouldn't be any other items
            # generated - but just in case there are (because of customizations), we'll simply
            # ignore these.
            return
        
        # first check that the clip has a shot name - otherwise things won't work!
        if info["shotName"] == "":
            QtGui.QMessageBox.warning(None,
                                      "Missing shot name!",
                                      ("The clip '%s' does not have a shot name and therefore cannot be exported. "
                                      "Please ensure that all shots you wish to exports "
                                      "have been named. " % info.get("name")) )
            
            # TODO: send the clip to the trash for now. no way to abort at this point
            # but we don't have enough information to be able to proceed at this point either
            info["resolvedPath"] = "flame_trash/unnamed_shot_%s" % uuid.uuid4().hex
            
            # TODO: can we avoid this export altogether?
            return
        
        # get the appropriate file system template
        if info.get("assetType") == "video":
            template = self.get_template("plate_template")
            
        elif info.get("assetType") == "batch":
            template = self.get_template("batch_template")
            
        elif info.get("assetType") == "batchOpenClip":
            template = self.get_template("shot_clip_template")            

        elif info.get("assetType") == "openClip":
            template = self.get_template("segment_clip_template")            
        
        self.log_debug("Attempting to resolve template %s..." % template)
        
        # resolve the template via the context
        context = self._shots[info["shotName"]]["context"]

        # resolve the fields out of the context
        self.log_debug("Resolving template %s using context %s" % (template, context))
        fields = context.as_template_fields(template)
        self.log_debug("Resolved context based fields: %s" % fields)
        
        if info.get("assetType") == "video":
            # handle the flame sequence token - it will come in as "[1001-1100]"
            re_match = re.search('(\[[0-9]+-[0-9]+\])\.', info["resolvedPath"])
            if not re_match:
                raise TankError("Cannot find frame number token in export data!")
            fields["SEQ"] = re_match.group(1)

        # create some fields based on the info in the info params                
        if "versionNumber" in info:
            fields["version"] = int(info["versionNumber"])
        
        fields["segment_name"] = info["assetName"]
            
        if "width" in info:
            fields["width"] = int(info["width"])

        if "height" in info:
            fields["height"] = int(info["height"])
        
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
        # key by both type and name (segment name) in order to guarantee uniqueness
        template_key = "%s_%s" % (info["assetType"], info["assetName"])
        self._shots[info["shotName"]][template_key] = (template, fields)
        
        
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
        asset_type = info.get("assetType") 
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
        context = self._shots[info["shotName"]]["context"]
        
        # given the template and fields we calculated in the pre-asset hook,
        # compute a shotgun-friendly path where the sequence identifier has 
        # been turned into a %04d-equivalent:
        template_key = "%s_%s" % (info["assetType"], info["assetName"])
        (template, fields) = self._shots[info["shotName"]][template_key]
        new_fields = copy.deepcopy(fields)
        new_fields["SEQ"] = "FORMAT: %d"
        toolkit_path = template.apply_fields(new_fields)        
        
        # figure out if the publishing process should also be setting
        # the thumbnail for the associated shot
        # see if the associated shot was created now
        shot_created = self._shots[info["shotName"]]["created"]
        # see if any other asset export as already flagged that they are doing the upload
        thumb_uploaded = self._shots[info["shotName"]].get("thumb_uploaded", False)
        # only consider uploading for video type assets
        if shot_created and asset_type == "video" and not thumb_uploaded:
            self._shots[info["shotName"]]["thumb_uploaded"] = True
            make_shot_thumb = True
        else:
            make_shot_thumb = False
        
        # now start preparing a remote job
        args = {"info": info, 
                "serialized_shot_context": sgtk.context.serialize(context),
                "toolkit_path": toolkit_path,
                "user_comments": self._user_comments,
                "make_shot_thumb": make_shot_thumb }
        
        # and populate backburner job parameters
        field_str = ", ".join(["%s %s" % (k,v) for (k,v) in fields.iteritems()])
        field_str += ", ".join(["%s %s" % (k,v) for (k,v) in info.iteritems()])
        
        backburner_job_title = "Shotgun Upload - %s, %s, %s" % (info["sequenceName"], 
                                                               info["shotName"], 
                                                               info["assetType"])

        backburner_job_desc = "Transcoding media, registering and uploading in Shotgun for %s" % field_str        
        
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
                        
        # now start assemble publish parameters
        args = {
            "tk": self.sgtk,
            "context": shot_context,
            "comment": user_comments,
            "path": toolkit_path,
            "name": "foo bar",
            "version_number": info.get("versionNumber"),
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
    
        
    def display_summary(self, session_id, info):
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
        # todo - replace with custom UI
        from PySide import QtGui, QtCore
        
        if self._submission_done:
            # things are cooking!
            QtGui.QMessageBox.information(None,
                                          "Shotgun submission complete!",
                                          "Submission complete! Quicktimes will be generated in the background and "
                                          "then uploaded to Shotgun.")

        else:
            # somewhere along the way, outside hooks, the process was cancelled or errored.
            QtGui.QMessageBox.warning(None,
                                      "Submission cancelled!",
                                      "Shotgun submission was cancelled or aborted. Nothing will be uploaded "
                                      "to Shotgun for review.")
            
        
        
        
        
        
