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

        # register our desired interaction with flame hooks
        menu_caption = self.get_setting("menu_name")
        
        # set up callbacks for the engine to trigger 
        # when this profile is being triggered 
        callbacks = {}
        callbacks["preCustomExport"] = self.pre_custom_export
        callbacks["preExportSequence"] = self.prepare_export_structure
        callbacks["preExportAsset"] = self.adjust_path
        callbacks["postExportAsset"] = self.register_post_asset_job
        
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
        # populate the host to use for the export. Currently hard coded to local
        info["destinationHost"] = "localhost"
        # let the export root path align with the primary project root
        info["destinationPath"] = self.sgtk.project_path
        # pick up the xml export profile from the configuration
        info["presetPath"] = self.execute_hook_method("settings_hook", "get_export_preset")
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
                
        self.log_debug("Preparing export structure for sequence %s and shots %s" % (sequence_name, shot_names))
        self.engine.show_busy("Preparing Shotgun...", "Preparing Shots for export...")
        
        try:

            task_template = self.get_setting("task_template")
            if task_template == "":
                task_template = None
    
            shots = self.execute_hook_method("settings_hook",
                                             "resolve_sg_shot_structure", 
                                             parent_name = info["sequenceName"], 
                                             shot_names = info["shotNames"], 
                                             shot_task_template = task_template)
            
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
           name:            Name of the exported asset.
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

        if info.get("assetType") == "openClip":
            # this asset is the sequence level clip xml file
            # for now, we don't publish this in Shotgun.
            info["resolvedPath"] = "shotgun_%s.xml" % uuid.uuid4().hex
            return
        
        if info.get("assetType") not in ["video", "batch", "batchOpenClip"]:
            # the review system ignores any other assets. The export profiles are defined
            # in the app's settings hook, so technically there shouldn't be any other items
            # generated - but just in case there are (because of customizations), we'll simply
            # ignore these.
            return
        
        # get the appropriate file system template
        if info.get("assetType") == "video":
            template = self.get_template("plate_template")
            
        elif info.get("assetType") == "batch":
            template = self.get_template("batch_template")
            
        elif info.get("assetType") == "batchOpenClip":
            template = self.get_template("clip_template")            
        
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
                
        if "versionNumber" in info:
            fields["version"] = info["versionNumber"]
        
        try:
            full_path = template.apply_fields(fields)
        except Exception, e:
            raise TankError("Could not resolve a file system path " 
                            "from template %s and fields %s: %s" % (template, fields, e))
        
        self.log_debug("Resolved %s -> %s" % (fields, full_path))
        
        # chop off the root of the path - the resolvedPath should be local to the destinationPath
        local_path = full_path[len(info["destinationPath"])+1:]
        
        self.log_debug("Chopping off root path %s -> %s" % (full_path, local_path))
        
        info["resolvedPath"] = local_path
        
        
        
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
        if info.get("assetType") not in ["video", "batch", "batchOpenClip"]:
            # the review system ignores any other assets. The export profiles are defined
            # in the app's settings hook, so technically there shouldn't be any other items
            # generated - but just in case there are (because of customizations), we'll simply
            # ignore these.
            return
        
        if info.get("isBackground"):
            run_after_job_id = info.get("backgroundJobId")
        else:
            run_after_job_id = None
        
        # set up the arguments which we will pass (via backburner) to 
        # the target method which gets executed
        args = {"info": info}
        
        # and populate UI params
        backburner_job_title = "Shot '%s' - Registering with Shotgun" % info.get("ShotName") 
        backburner_job_desc = "Transcoding media, registering and uploading in Shotgun."        
        
        # kick off async job
        self.engine.create_local_backburner_job(backburner_job_title, 
                                                backburner_job_desc, 
                                                run_after_job_id,
                                                self, 
                                                "populate_shotgun",
                                                args)

    def populate_shotgun(self, info):
        """
        Called when an item has been exported
        
        :param session_id: String which identifies which export session is being referred to
        :param info: metadata dictionary for the publish
        """
        
        if info.get("assetType") == "video":
            publish_type = self.get_setting("plate_publish_type")
            
        elif info.get("assetType") == "batch":
            publish_type = self.get_setting("batch_publish_type")
            
        elif info.get("assetType") == "batchOpenClip":
            publish_type = self.get_setting("clip_publish_type")
            
        else:
            raise TankError("Unsupported asset type '%s'" % info.get("assetType"))
        
        # resolve the template via the context
        context = self._get_context(info)
        
        # now assemble the path in a toolkit friendly format
        # we get this sort of input data
        # 'destinationPath': '/mnt/projects/flame_testing', 
        # 'resolvedPath': 'sequences/X-Ball_Gladiator_3/sh_0010/plates/sh_0010.[00000265-00000324].dpx', 
        
        full_path = os.path.join(info.get("destinationPath"), info.get("resolvedPath"))
        # find the [xxx-xxx] pattern and replace it with %04d
        
        # todo - hopefully we can get the frame padding option across into the hook
        # [0265-0324].dpx -> %04d.dpx
        # [00265-00324].dpx -> %05d.dpx
        # [000265-000324].dpx -> %06d.dpx
        # [0212312312365-123324].dpx -> %d.dpx
        full_path = re.sub('\[[0-9]{4}-[0-9]{4}\]', '%04d', full_path)
        full_path = re.sub('\[[0-9]{5}-[0-9]{5}\]', '%05d', full_path)
        full_path = re.sub('\[[0-9]{6}-[0-9]{6}\]', '%06d', full_path)
        full_path = re.sub('\[[0-9]{7}-[0-9]{7}\]', '%07d', full_path)
        # and the catch-all
        full_path = re.sub('\[[0-9]+-[0-9]+\]', '%d', full_path)
        
        self.log_debug("Translated paths %s %s --> %s" % (info.get("destinationPath"), 
                                                          info.get("resolvedPath"), 
                                                          full_path))
        
        # now compile the name of the publish. This is done on the form
        # name.ext, where ext is the file extension of the published file
        # and the name part is intelligently derived from the input data
        if info.get("shotName"):
            file_name = info.get("shotName")
        elif info.get("sequenceName"):
            file_name = info.get("sequenceName")
        elif info.get("assetName"):
            file_name = info.get("assetName")
        else:
            file_name = "unknown"
            
        (_, ext) = os.path.splitext(full_path)
        publish_name = "%s.%s" % (file_name, ext)
        
        args = {
            "tk": self.sgtk,
            "context": context,
            "comment": "Created by the Shotgun to Flame Exporter.",
            "path": full_path,
            "name": publish_name,
            "version_number": info.get("versionNumber"),
            # "thumbnail_path": thumbnail_path,
            # "task": sg_task,                            <------ todo: assign with configurable task?
            # "dependency_paths": dependency_paths,
            "published_file_type": publish_type,
        }
        
        self.log_debug("Register publish in shotgun: %s" % str(args))
        
        # register publish
        # TODO - check for existing publishes on disk!
        #        it is possible that the publish is overriding a previous publish
        sg_data = sgtk.util.register_publish(**args)
        
        self.log_debug("Register complete: %s" % sg_data)
        
        if info.get("assetType") == "video":
            # register version!
            self.log_debug(">>>>>>>>>>>>>>>>>>>>> VERSION")
    
        
        
        
        
        
        
