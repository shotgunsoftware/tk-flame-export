# Copyright (c) 2014 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk


class SegmentMetadata(object):
    """
    Simple Value wrapper class which holds properties associated with a timeline segment.
    """
    
    def __init__(self, name):
        """
        Constructor
        """
        
        self.name = name
        
        self.video_metadata = None
        self.batch_metadata = None
        
        self.shotgun_version = None
        
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

        self.shotgun_id = None              # shotgun shot id
        
        self.shotgun_cut_in = None          # shotgun cut in 
        self.shotgun_cut_out = None         # shotgun cut out
        self.shotgun_cut_order = None       # shotgun cut order
        
        self.new_cut_in = None              # calculated cut in
        self.new_cut_out = None             # calculated cut out
        self.new_cut_order = None           # calculated cut order
        
        self.context = None                 # context object for the shot
        
        self.segment_metadata = {}          # metadata about all the clips associated 
                                            # with this shot, keyed by segment name
        
        
        # internal members
        self.__thumb_upload_handled = False
                
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
    
    def update_new_cut_info(self, record_in, record_out):
        """
        Updates the shot cut information based on segment cut information received from Flame.
        
        The frame information coming from Flame includes handles and is out frame exclusive, 
        meaning that the sequence 1,2,3,4,5 is denoted 1-6. 
        
        :param record_in: Record in parameter for a segment in flame belonging to this shot
        :param record_out: Record out parameter for a segment in flame belonging to this shot
        """
        
        app = sgtk.platform.current_bundle()
        
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
