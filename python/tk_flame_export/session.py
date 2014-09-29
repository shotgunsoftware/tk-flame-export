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
        """
        self._app = sgtk.platform.current_bundle()
        self._profile = profile
        
        self._sequence = None
        self._shots = {}
        
    def get_destination_path(self):
        
        return "/tmp"
    
    
    def get_export_preset_path(self):
        
        #return "/usr/discreet/flameassist_2015.2.pr99/export/presets/file_sequence/Jpeg (8-bit).xml"
        return "/usr/discreet/flameassist_2015.2.pr99/export/presets/sequence_publish/EDL Publish (8-bit DPX and WAVE).xml"
        
        
    def prepare_export_structure(self, sequence_name, shot_names):
        
        self._app.log_debug("Preparing export structure for sequence %s and shots %s" % (sequence_name, shot_names))

        sg = self._app.shotgun

        # first, ensure that the sequence exists in Shotgun
        self._sequence = sg.find_one("Sequence", [["code", "is", sequence_name],
                                                  ["project", "is", self._app.context.project]])
        if not self._sequence:
            self._sequence = sg.create("Sequence", {"code": sequence_name, 
                                                    "description": "Created by the Shotgun Toolkit Flame exporter.",
                                                    "project": self._app.context.project})
            # todo: add thumbnail
            

        new_shot_ids = []
        
        for shot_name in shot_names:

            shot = sg.find_one("Shot", [["code", "is", shot_name],
                                        ["sg_sequence", "is", self._sequence]])
            if not shot:
                shot = sg.create("Shot", {"code": shot_name, 
                                          "description": "Created by the Shotgun Toolkit Flame exporter.",
                                          "sg_sequence": self._sequence,
                                          "project": self._app.context.project})
                
                new_shot_ids.append(shot["id"])
            
            self._shots[shot_name] = shot
            

        self._app.sgtk.create_filesystem_structure("Shot", new_shot_ids, engine="tk-flame")
        
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
        
