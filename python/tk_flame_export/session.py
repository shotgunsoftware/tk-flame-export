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
        
        self._sequence = None
        self._shots = {}
        
    def get_destination_path(self):
        
        # return the primary project root by default 
        return self._app.sgtk.project_path
    
    
    def get_export_preset_path(self):
        
        return self._profile["export_template"]        
        
    def prepare_export_structure(self, sequence_name, shot_names):
        
        self._app.log_debug("Preparing export structure for sequence %s and shots %s" % (sequence_name, shot_names))

        self._app.engine.show_busy("Creating Shotgun Structure...", 
                                   "Preparing Sequence '%s'..." % sequence_name)

        sg = self._app.shotgun

        # first, ensure that the sequence exists in Shotgun
        self._sequence = sg.find_one("Sequence", [["code", "is", sequence_name],
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
                
            self._sequence = sg.create("Sequence", {"code": sequence_name, 
                                                    "description": "Created by the Shotgun Toolkit Flame exporter.",
                                                    "task_template": sequence_template,
                                                    "project": self._app.context.project})
            # todo: add thumbnail
            

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
            
            self._shots[shot_name] = shot
            
        for (shot_id, shot_name) in new_shots.iteritems():
            
            self._app.engine.show_busy("Creating Shotgun Structure...", 
                                       "Creating folders for Shot '%s'..." % shot_name)
            
            self._app.sgtk.create_filesystem_structure("Shot", shot_id, engine="tk-flame")
        
    def register_publish(self, info):
        """
        Register a file exported 
        
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
           versionName:     Current version name of export (Empty if unversioned).
           versionNumber:   Current version number of export (0 if unversioned).
        
        """
        pass
        
        
        # [PYTHON HOOK] Calling python hook function postExportAsset(
        # {'height': 1080L, 
        #  'destinationPath': '/tmp', 'destinationHost': 'Mannes-MacBook-Pro-2.local', 'sourceOut': 432L, 'assetType': 'video', 'recordIn': 0L, 'sequenceFps': '23.976', 'width': 1920L, 'fps': '23.976', 'resolvedPath': 'X-Ball Gladiator 3_publish_publish_publish_publish_publish_publish_publish_publish_publish_publish/IMPORT/1920x1080/s0014.[00000430-00000431].dpx', 'sequenceName': 'X-Ball Gladiator 3_publish_publish_publish_publish_publish_publish_publish_publish_publish_publish', 'shotName': 'sh_0010', 'assetName': '010_Jump_Sand', 'versionNumber': 0L, 'versionName': 'v<version>', 'recordOut': 2L, 'sourceIn': 430L, 'scanFormat': 'PROGRESSIVE', 'namePattern': '<name>/<tape>/<width>x<height>/s<segment>.<timecode><ext>', 'depth': '8-bit', 'isBackground': False, 'aspectRatio': 1.7777777910232544})
      
      
    
#    assetType = info.get( "assetType" )
#    if ( assetType not in [ "video", "batch", "openClip", "batchOpenClip" ] ): return
# 
#    # If the export is foreground, accumulate the asset and update shotgun
#    # at the end of the export process to increase performace
#    #
#    if ( not info.get( "isBackground", False ) ):
#       userData[ "assetList" ][ assetType ].append( info )
# 
#    else:
#       if ( assetType == "video" ):
#          sgUtil.createVersions( project = project,
#                                 versionList = [ info ],
#                                 shotList = shots )
#       elif ( assetType == "batch" ):
#          sgUtil.createBatchAssets( project = project,
#                                    batchSetupList = [ info ],
#                                    shotList = shots )
#       elif ( assetType == "openClip" ):
#          # FIXME Create entity in Shotgun
#          pass
#       elif ( assetType == "batchOpenClip" ):
#          # FIXME Create entity in Shotgun
#          pass
        
    
        
    def post_process_export(self):
        
        self._app.log_debug("post_process_export!")
        
        
        #    # Bulk create shots versions and batch setup assets
        #    #
        #    versions = sgUtil.createVersions( project = project,
        #                                      versionList = assets.get( "video" ),
        #                                      shotList = shots )
        #    setups   = sgUtil.createBatchAssets( project = project,
        #                                         batchSetupList = assets.get( "batch" ),
        #                                         shotList = shots )
        
