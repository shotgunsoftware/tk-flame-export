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
    """
    Export functionality to automate and streamline content export out of Flame.
    """
    
    def init_app(self):
        """
        Called as the application is being initialized.
        """
        self.log_debug("%s: Initializing" % self)

        # keep track of the shotgun sequence and shots that the export
        # items are associated with
        self._sequence = None
        self._shots = {}
        
        # register our desired interaction with flame hooks
        menu_caption = self.get_setting("profile_name")
        
        # set up callbacks for the engine to trigger 
        # when this profile is being triggered 
        callbacks = {}
        callbacks["preCustomExport"] = self.pre_custom_export
        callbacks["preExportSequence"] = self.prepare_export_structure
        callbacks["preExportAsset"] = self.adjust_path
        callbacks["postExportAsset"] = self.register_publish
        #callbacks["postCustomExport"] = x
        
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
        info["presetPath"] = self.get_setting("flame_export_preset")    
        self.log_debug("%s: Starting custom export session with preset '%s'" % info["presetPath"])


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

        self.engine.show_busy("Creating Shotgun Structure...", "Preparing Sequence '%s'..." % sequence_name)

        sg = self.shotgun

        # first, ensure that the sequence exists in Shotgun
        self._sequence = {}
        sg_sequence_data = sg.find_one("Sequence", [["code", "is", sequence_name],
                                                   ["project", "is", self.context.project]]) 
        
        if sg_sequence_data:
            self._sequence["shotgun"] = sg_sequence_data 
        
        else:    
            
            # Create a new sequence in Shotgun
            # First see if we should assign a task template
            sequence_task_template_name = self.get_setting("sequence_task_template")
            sequence_template = None
            if sequence_task_template_name: 
                sequence_template = sg.find_one("TaskTemplate", [["code", "is", sequence_task_template_name]])
                if not sequence_template:
                    raise TankError("The task template '%s' specified in the sequence_task_template setting "
                                    "does not exist!" % sequence_task_template_name)
                
            self._sequence["shotgun"] = sg.create("Sequence", {"code": sequence_name, 
                                                    "description": "Created by the Shotgun Toolkit Flame exporter.",
                                                    "task_template": sequence_template,
                                                    "project": self.context.project})
            

        new_shots = {}
        
        for shot_name in shot_names:

            self.engine.show_busy("Creating Shotgun Structure...", 
                                       "Preparing Shot '%s'..." % shot_name)

            shot = sg.find_one("Shot", [["code", "is", shot_name],
                                        ["sg_sequence", "is", self._sequence["shotgun"] ]])
            if not shot:
                
                # Create a new shot in Shotgun
                # First see if we should assign a task template
                shot_task_template_name = self.get_setting("shot_task_template")
                sequence_template = None
                if shot_task_template_name: 
                    shot_template = sg.find_one("TaskTemplate", [["code", "is", shot_task_template_name]])
                    if not shot_template:
                        raise TankError("The task template '%s' specified in the shot_task_template setting "
                                        "does not exist!" % shot_task_template_name)

                shot = sg.create("Shot", {"code": shot_name, 
                                          "description": "Created by the Shotgun Toolkit Flame exporter.",
                                          "sg_sequence": self._sequence["shotgun"],
                                          "task_template": shot_template,
                                          "project": self.context.project})
                
                new_shots[ shot["id"] ] = shot_name 
            
            self._shots[shot_name] = {}
            self._shots[shot_name]["shotgun"] = shot
        
        # run folder creation for our newly created shots    
        for (shot_id, shot_name) in new_shots.iteritems():
            
            self.engine.show_busy("Creating Shotgun Structure...", 
                                  "Creating folders for Shot '%s'..." % shot_name)
            
            self.sgtk.create_filesystem_structure("Shot", shot_id, engine="tk-flame")
        
        # lastly, establish a context for all objects
        sg_sequence_id = self._sequence["shotgun"]["id"]
        self._sequence["context"] = self.sgtk.context_from_entity("Sequence", sg_sequence_id)

        for shot_name in self._shots:
            sg_shot_id = self._shots[shot_name]["shotgun"]["id"]
            self._shots[shot_name]["context"] = self.sgtk.context_from_entity("Shot", sg_shot_id)   
    
    
    
    
    
    
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
            context = self.context

        return context
    
    
    
    
    def adjust_path(self, session_id, info):
        """
        Called when an item is about to be exported and a path needs to be computed

        :param session_id: String which identifies which export session is being referred to
        :param info: metadata dictionary for the publish        
        """
        
        # get the appropriate file system template
        
        if info.get("assetType") == "video":
            template = self.get_template(self.get_setting("video_template"))
            
        elif info.get("assetType") == "batch":
            template = self.get_template(self.get_setting("batch_template"))
            
        elif info.get("assetType") == "audio":
            template = self.get_template(self.get_setting("audio_template"))
        
        elif info.get("assetType") == "sequence":
            template = self.get_template(self.get_setting("edl_template"))
        
        elif info.get("assetType") == "openClip":
            template = self.get_template(self.get_setting("sequence_clip_template"))
        
        elif info.get("assetType") == "batchOpenClip":
            template = self.get_template(self.get_setting("shot_clip_template"))
            
        else:
            self.log_debug("Ignoring unsupported flame asset type '%s'" % info.get("assetType"))
            return
        
        self.log_debug("Attempting to resolve template %s..." % template )
        
        # resolve the template via the context
        context = self._get_context(info)

        # resolve the fields out of the context
        fields = context.as_template_fields(template)

        self.log_debug("Resolved context based fields: %s" % fields)
        
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
        
        
        
        
        
        
        
        
    def register_publish(self, session_id, info):
        """
        Called when an item has been exported
        
        :param session_id: String which identifies which export session is being referred to
        :param info: metadata dictionary for the publish
        """        

        
        if info.get("assetType") == "video":
            publish_type = self.get_setting("video_publish_type")
            
        elif info.get("assetType") == "batch":
            publish_type = self.get_setting("batch_publish_type")
            
        elif info.get("assetType") == "audio":
            publish_type = self.get_setting("audio_publish_type")
        
        elif info.get("assetType") == "sequence":
            publish_type = self.get_setting("edl_publish_type")
        
        elif info.get("assetType") == "openClip":
            publish_type = self.get_setting("clip_publish_type")
        
        elif info.get("assetType") == "batchOpenClip":
            publish_type = self.get_setting("clip_publish_type")
            
        else:
            self.log_debug("Ignoring unsupported flame asset type '%s'" % info.get("assetType"))
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
    
        
        
        
        
        
        
