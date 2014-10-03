# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
from sgtk import TankError
import os
import re
import sys


class ExportSession(object):
    """
    Represents an export session in flame.
    """
    
    #########################################################################################################
    # public methods
    
    def __init__(self, profile):
        """
        Construction
        
        :param profile: Configuration data for the profile. A dictionary with the following keys: 
                        - display_name
                        - export_template
                        - video_publish_type
                        - batch_publish_type
                        - edl_publish_type
                        - audio_publish_type
        """
        self._app = sgtk.platform.current_bundle()
        self._profile = profile
        
        # keep track of the shotgun sequence and shots that the export
        # items are associated with
        self._sequence = None
        self._shots = {}
        
    def get_destination_path(self):
        
        # return the primary project root by default 
        return self._app.sgtk.project_path
    
    def get_export_preset_path(self):
        
        return self._profile["export_template"]        
        
    def prepare_export_structure(self, sequence_name, shot_names):
        
        self._app.log_debug("Preparing export structure for sequence %s and shots %s" % (sequence_name, shot_names))

        self._app.engine.show_busy("Creating Shotgun Structure...", "Preparing Sequence '%s'..." % sequence_name)

        sg = self._app.shotgun

        # first, ensure that the sequence exists in Shotgun
        self._sequence = {}
        self._sequence["shotgun"] = sg.find_one("Sequence", [["code", "is", sequence_name],
                                                ["project", "is", self._app.context.project]]) 
        
        if not self._sequence:
            
            # Create a new sequence in Shotgun
            # First see if we should assign a task template
            sequence_task_template_name = self._app.get_setting("sequence_task_template")
            sequence_template = None
            if sequence_task_template_name: 
                sequence_template = sg.find_one("TaskTemplate", [["code", "is", sequence_task_template_name]])
                if not sequence_template:
                    raise TankError("The task template '%s' specified in the sequence_task_template setting "
                                    "does not exist!" % sequence_task_template_name)
                
            self._sequence["shotgun"] = sg.create("Sequence", {"code": sequence_name, 
                                                    "description": "Created by the Shotgun Toolkit Flame exporter.",
                                                    "task_template": sequence_template,
                                                    "project": self._app.context.project})
            

        new_shots = {}
        
        for shot_name in shot_names:

            self._app.engine.show_busy("Creating Shotgun Structure...", 
                                       "Preparing Shot '%s'..." % shot_name)

            shot = sg.find_one("Shot", [["code", "is", shot_name],
                                        ["sg_sequence", "is", self._sequence]])
            if not shot:
                
                # Create a new shot in Shotgun
                # First see if we should assign a task template
                shot_task_template_name = self._app.get_setting("shot_task_template")
                sequence_template = None
                if shot_task_template_name: 
                    shot_template = sg.find_one("TaskTemplate", [["code", "is", shot_task_template_name]])
                    if not shot_template:
                        raise TankError("The task template '%s' specified in the shot_task_template setting "
                                        "does not exist!" % shot_task_template_name)

                shot = sg.create("Shot", {"code": shot_name, 
                                          "description": "Created by the Shotgun Toolkit Flame exporter.",
                                          "sg_sequence": self._sequence,
                                          "task_template": shot_template,
                                          "project": self._app.context.project})
                
                new_shots[ shot["id"] ] = shot_name 
            
            self._shots[shot_name] = {}
            self._shots[shot_name]["shotgun"] = shot
        
        # run folder creation for our newly created shots    
        for (shot_id, shot_name) in new_shots.iteritems():
            
            self._app.engine.show_busy("Creating Shotgun Structure...", 
                                       "Creating folders for Shot '%s'..." % shot_name)
            
            self._app.sgtk.create_filesystem_structure("Shot", shot_id, engine="tk-flame")
        
        # lastly, establish a context for all objects
        sg_sequence_id = self._sequence["shotgun"]["id"]
        self._sequence["context"] = self._app.sgtk.context_from_entity("Sequence", sg_sequence_id)

        for shot_name in self._shots:
            sg_shot_id = self._shots[shot_name]["shotgun"]["id"]
            self._shots[shot_name]["context"] = self._app.sgtk.context_from_entity("Shot", sg_shot_id)   
        
        
    def _get_context(self, info):
        """
        Given a std info dict, return a suitable context
        """
        # create a context for the object!
        # see if this is a shot
        shot_name = info.get("shotName")
        sequence_name = info.get("sequenceName")
        
        if shot_name in self._shots:
            # this asset belongs to a shot!
            context = self._shots[shot_name]["context"]
        
        elif sequence_name:
            # this asset is not part of a shot but part of a sequence
            context = self._sequence["context"]
        
        else:
            # if an asset is coming our way and it's not part of a squence nor shot,
            # assign it the current context (typically a project context)
            context = self._app.context

        return context
        
    def adjust_path(self, info):
        """
        Adjust the path for an export item
        
        :param info: Dictionary with a number of parameters:
        
           destinationHost: Host name where the exported files will be written to.
           destinationPath: Export path root.
           namePattern:     List of optional naming tokens.
           resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
           assetName:       Name of the exported asset.
           sequenceName:    Name of the sequence the asset is part of.
           shotName:        Name of the shot the asset is part of.
           trackName:       Track name the asset is part of in the sequence.
           assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
           
           isBackground:    True if the export of the asset happened in the background.
           backgroundJobId: Id of the background job given by the backburner manager upon submission. 
                            Empty if job is done in foreground.
           
           width:           Frame width of the exported asset.
           height:          Frame height of the exported asset.
           aspectRatio:     Frame aspect ratio of the exported asset.
           depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
           scanFormat:      Scan format of the exported asset. ( 'FIELD_1', 'FIELD_2', 'PROGRESSIVE' )
           
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).
           
           fps:             Frame rate of exported asset.
           sequenceFps:     Frame rate of the sequence the asset is part of.
           segmentIndex:    Asset index (1 based) in the track.
           sourceIn:        Source in point in frame and asset frame rate.
           sourceOut:       Source out point in frame and asset frame rate.
           recordIn:        Record in point in frame and sequence frame rate.
           recordOut:       Record out point in frame and sequence frame rate.
        
        :returns: An updated path
        """
        
        # get the appropriate file system template
        
        if info.get("assetType") == "video":
            template = self._app.get_template(self._profile["video_template"])
            
        elif info.get("assetType") == "batch":
            template = self._app.get_template(self._profile["batch_template"])
            
        elif info.get("assetType") == "audio":
            template = self._app.get_template(self._profile["audio_template"])
        
        elif info.get("assetType") == "sequence":
            template = self._app.get_template(self._profile["edl_template"])
        
        elif info.get("assetType") == "openClip":
            template = self._app.get_template(self._profile["clip_template"])
        
        elif info.get("assetType") == "batchOpenClip":
            template = self._app.get_template(self._profile["clip_template"])
            
        else:
            self._app.log_debug("Ignoring unsupported flame asset type '%s'" % info.get("assetType"))
            return
        
        self._app.log_debug("Attempting to resolve template %s..." % template )
        
        # resolve the template via the context
        context = self._get_context(info)

        # resolve the fields out of the context
        fields = context.as_template_fields(template)

        self._app.log_debug("Resolved context based fields: %s" % fields)
        
        # handle the flame sequence
        # todo: better handling of this
        # todo: read xml file to determine zero padding of values
        # 'resolvedPath': 'sequences/X-Ball_Gladiator_3/sh_0010/plates/sh_0010.[00000265-00000324].dpx',
        if "sourceIn" in info and "sourceOut" in info:
            fields["FLAMESEQ"] = "[%04d-%04d]" % (info["sourceIn"], info["sourceOut"]-1)
        
        if "versionNumber" in info:
            fields["version"] = info["versionNumber"]
        
        # todo: validate!
        
        return template.apply_fields(fields)
        
        
        
        
    def register_publish(self, info):
        """
        Register a file exported 
        
        :param info: Dictionary with a number of parameters:
        
           destinationHost: Host name where the exported files will be written to.
           destinationPath: Export path root.
           namePattern:     List of optional naming tokens.
           resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
           assetName:       Name of the exported asset.
           sequenceName:    Name of the sequence the asset is part of.
           shotName:        Name of the shot the asset is part of.
           trackName:       Track name the asset is part of in the sequence.
           assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
           
           isBackground:    True if the export of the asset happened in the background.
           backgroundJobId: Id of the background job given by the backburner manager upon submission. 
                            Empty if job is done in foreground.
           
           width:           Frame width of the exported asset.
           height:          Frame height of the exported asset.
           aspectRatio:     Frame aspect ratio of the exported asset.
           depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
           scanFormat:      Scan format of the exported asset. ( 'FIELD_1', 'FIELD_2', 'PROGRESSIVE' )
           
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).
           
           fps:             Frame rate of exported asset.
           sequenceFps:     Frame rate of the sequence the asset is part of.
           segmentIndex:    Asset index (1 based) in the track.
           sourceIn:        Source in point in frame and asset frame rate.
           sourceOut:       Source out point in frame and asset frame rate.
           recordIn:        Record in point in frame and sequence frame rate.
           recordOut:       Record out point in frame and sequence frame rate.
        
        """
        
        # Example of info parameter data {
        # 'height': 1080L, 
        # 'destinationPath': '/mnt/projects/flame_testing', 
        # 'destinationHost': 'Mannes-MacBook-Pro-2.local', 
        # 'sourceOut': 325L, 
        # 'assetType': 'video',
        # 'recordIn': 0L, 
        # 'sequenceFps': '23.976', 
        # 'width': 1920L, 
        # 'fps': '23.976', 
        # 'resolvedPath': 'sequences/X-Ball_Gladiator_3/sh_0010/plates/sh_0010.[00000265-00000324].dpx', 
        # 'sequenceName': 'X-Ball Gladiator 3', 
        # 'shotName': 'sh_0010', 
        # 'assetName': '008_Tilt_Up_Left', 
        # 'versionNumber': 0L, 
        # 'versionName': 'v<version>', 
        # 'recordOut': 60L, 
        # 'sourceIn': 265L, 
        # 'scanFormat': 'PROGRESSIVE', 
        # 'namePattern': 'sequences/<name>/<shot name>/plates/<shot name><timecode><ext>', 
        # 'depth': '8-bit', 
        # 'isBackground': False, 
        # 'aspectRatio': 1.7777777910232544 }
        
        if info.get("assetType") == "video":
            publish_type = self._profile["video_publish_type"]
            
        elif info.get("assetType") == "batch":
            publish_type = self._profile["batch_publish_type"]
            
        elif info.get("assetType") == "audio":
            publish_type = self._profile["audio_publish_type"]
        
        elif info.get("assetType") == "sequence":
            publish_type = self._profile["edl_publish_type"]
        
        elif info.get("assetType") == "openClip":
            publish_type = self._profile["clip_publish_type"]
        
        elif info.get("assetType") == "batchOpenClip":
            publish_type = self._profile["clip_publish_type"]
            
        else:
            self._app.log_debug("Ignoring unsupported flame asset type '%s'" % info.get("assetType"))
            return
        
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
        
        self._app.log_debug("Translated paths %s %s --> %s" % (info.get("destinationPath"), 
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
            "tk": self._app.sgtk,
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
        
        self._app.log_debug("Register publish in shotgun: %s" % str(args))
        
        # register publish
        # TODO - check for existing publishes on disk!
        #        it is possible that the publish is overriding a previous publish
        sg_data = sgtk.util.register_publish(**args)
        
        self._app.log_debug("Register complete: %s" % sg_data)
        
        if info.get("assetType") == "video":
            # register version!
            self._app.log_debug(">>>>>>>>>>>>>>>>>>>>> VERSION")
    
        
    def post_process_export(self):
        
        self._app.log_debug("post_process_export!")
        
        
        
