# Copyright (c) 2014 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from sgtk import TankError

class SegmentMetadata(object):
    """
    Simple Value wrapper class which holds properties associated with a timeline segment.
    """
    
    def __init__(self):
        """
        Constructor
        """        
        self.video_info = None          # info dictionary (as sent from flame) for the video portion of this segment
        self.shotgun_version = None     # associated shotgun version (dict with type/id)
        
    def has_shotgun_version(self):
        """
        Returns true if a shotgun version exists for the render associated with this segment.
        If a shotgun version exists, it is implied that a render also exists
        
        :returns: boolean flag
        """
        return self.shotgun_version is not None
        
    def get_shotgun_version_id(self):
        """
        Returns the shotgun id for the version associated with this segment, if there is one.
        
        :returns: shotgun version id as int
        """
        if not self.has_shotgun_version():
            raise TankError("Cannot get shotgun version id for segment - no version associated!")
        return self.shotgun_version["id"]
    
    def has_render_export(self):
        """
        Returns true if a render export is associated with this segment, false if not.
        
        It is possible that an export doesn't have a render file exported if flame for example
        prompts the user, asking her/him if they want to override an existing file and they 
        select 'no'
        
        :return: bool flag
        """
        return self.video_info is not None
        
    def get_render_version_number(self):
        """
        Return the version number associated with the render file
        
        :returns: version number as int
        """        
        if not self.has_render_export():
            raise TankError("Cannot get render path for segment - no video metadata found!")

        return int(self.video_info["versionNumber"])
    
    def get_render_path(self):
        """
        Return the export render path for this segment
        
        :returns: path string
        """
        if not self.has_render_export():
            raise TankError("Cannot get render path for segment - no video metadata found!")
        
        return os.path.join(self.video_info.get("destinationPath"), self.video_info.get("resolvedPath"))

        
        
        
        
class ShotMetadata(object):
    """
    Simple value wrapper class which holds various properties associated with a shot.
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
        
        self.created_this_session = False   # was the shotgun shot created in this export session?
        self.thumbnail_uploaded = False     # for new shots, has a thumbnail been pushed to Shotgun?

        self.shotgun_id = None              # shotgun shot id
        
        self.shotgun_cut_in = None          # shotgun cut in 
        self.shotgun_cut_out = None         # shotgun cut out
        self.shotgun_cut_order = None       # shotgun cut order
        
        self.new_cut_in = None              # calculated cut in
        self.new_cut_out = None             # calculated cut out
        self.new_cut_order = None           # calculated cut order
        
        self.context = None                 # context object for the shot
        
        self.batch_info = None              # info dictionary (as sent from flame) for the batch export
                                            # associated with this shot
        
        self.segment_metadata = {}          # metadata about all the clips associated 
                                            # with this shot, keyed by segment name                
    
    def has_batch_export(self):
        """
        Returns true if a batch export is associated with this shot, false if not.
        
        It is possible that an export doesn't have a batch file exported if flame for example
        prompts the user, asking her/him if they want to override an existing file and they 
        select 'no'
        
        :return: bool flag
        """
        return self.batch_info is not None
    
    def get_batch_path(self):
        """
        Return the batch export path for this shot
        
        :returns: path string
        """
        if not self.has_batch_export():
            raise TankError("Cannot get batch path - no batch metadata found!")
        
        return os.path.join(self.batch_info.get("destinationPath"), self.batch_info.get("resolvedPath"))
    
    def get_batch_version_number(self):
        """
        Return the version number associated with the batch file
        
        :returns: version number as int
        """        
        if not self.has_batch_export():
            raise TankError("Cannot get batch path - no batch metadata found!")

        return int(self.batch_info["versionNumber"])
    
    def update_new_cut_info(self, record_in, record_out):
        """
        Updates the shot cut information based on segment cut information received from Flame.
        
        The frame information coming from Flame includes handles and is out frame exclusive, 
        meaning that the sequence 1,2,3,4,5 is denoted 1-6. 
        
        :param record_in: Record in parameter for a segment in flame belonging to this shot
        :param record_out: Record out parameter for a segment in flame belonging to this shot
        """
        
        # the cut in and cut out are reflected by the values stored in the conform
        # in flame. These are sometimes defaulted to 10:00:00.00 so there may be some
        # large numbers here.
        cut_in = record_in 
        cut_out = record_out 
        
        # now, note that flame is cut-out-exclusive, meaning that the out frame
        # is actually not the last frame played back but the frame after that.
        # in the shotgun universe, we want last frame *inclusive* instead
        cut_out = cut_out - 1
        
        # now it is time to update the *SHOT* lengths. With Flame's collating,
        # a single shot may be made up of several *segments*. The cut information
        # we are getting from flame is per segment. We need to "grow" the shot range
        # so that it will encompass all segments.
        if self.new_cut_in is None:
            # no value yet
            self.new_cut_in = cut_in
        
        elif self.new_cut_in > cut_in:
            # we got a value but our current clip started before
            # the other. We want to capture the maximum range of 
            # the shot, so update
            self.new_cut_in = cut_in
            
        if self.new_cut_out is None:
            # no value yet
            self.new_cut_out = cut_out
            
        elif self.new_cut_out < cut_out:
            # we got a value but our current clip ended after
            # the other. We want to capture the maximum range of 
            # the shot, so update
            self.new_cut_out = cut_out
