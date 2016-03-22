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

from .segment import Segment

class Shot(object):
    """
    Represents a Shot in Flame and Shotgun.
    """

    def __init__(self, parent, name):
        """
        Constructor

        :param name: Name of the Shot
        """
        # set up the basic properties of this value wrapper
        self._app = sgtk.platform.current_bundle()

        self._name = name
        self._parent = parent
        self._created_this_session = False
        self._context = None
        self._shotgun_id = None
        self._sg_cut_in = None
        self._sg_cut_out = None
        self._sg_cut_order = None
        self._flame_batch_data = None
        self._segments = {}

    def __repr__(self):
        return "<Shot %s, %s>" % (self._name, self._parent)

    @property
    def new_in_shotgun(self):
        """
        True if this object was created in Shotgun as part of this session.
        """
        return self._created_this_session

    @property
    def name(self):
        """
        Returns the name of the sequence
        """
        return self._name

    @property
    def context(self):
        """
        Returns the name of the sequence
        """
        return self._context

    @property
    def shotgun_id(self):
        """
        Shotgun id for this Shot
        """
        return self._shotgun_id

    @property
    def segments(self):
        """
        List of segment objects for this shot
        """
        return self._segments.values()

    @property
    def exists_in_shotgun(self):
        """
        Returns true if the shot has an associated shotgun id
        """
        return self._shotgun_id is not None

    @property
    def has_batch_export(self):
        """
        Returns true if a batch export is associated with this shot, false if not.

        It is possible that an export doesn't have a batch file exported if Flame for example
        prompts the user, asking her/him if they want to override an existing file and they
        select 'no'
        """
        return self._flame_batch_data is not None

    @property
    def batch_path(self):
        """
        Return the flame batch export path for this shot
        """
        if not self.has_batch_export:
            raise TankError("Cannot get batch path - no batch metadata found!")

        return os.path.join(
            self._flame_batch_data.get("destinationPath"),
            self._flame_batch_data.get("resolvedPath")
        )

    @property
    def batch_version_number(self):
        """
        Return the version number associated with the batch file
        """
        if not self.has_batch_export:
            raise TankError("Cannot get batch path - no batch metadata found!")

        return int(self._flame_batch_data["versionNumber"])

    def set_sg_data(self, sg_data, new_in_shotgun):
        """
        Set shotgun data associated with this shot.

        The input shotgun data dict needs to contain at least
        the following keys: id, sg_cut_in, sg_cut_out, sg_cut_order

        :param sg_data: Shotgun dictionary with
        :param new_in_shotgun: Boolean to indicate if this shot was just created.
        """
        self._created_this_session = new_in_shotgun
        self._shotgun_id = sg_data["id"]
        self._sg_cut_in = sg_data["sg_cut_in"]
        self._sg_cut_out = sg_data["sg_cut_out"]
        self._sg_cut_order = sg_data["sg_cut_order"]

    def cache_context(self):
        """
        Computes the context for this Shot and caches it locally.
        """
        self._app.log_debug("Caching context for %s" % self)
        self._context = self._app.sgtk.context_from_entity("Shot", self.shotgun_id)

    def add_segment(self, segment_name):
        """
        Adds a segment to this Shot.

        :param segment_name: Name of segment to add
        :returns: Segment object
        """
        self._segments[segment_name] = Segment(self, segment_name)

    def set_flame_batch_data(self, data):
        """
        Specify the flame hook data dictionary for this shot

        :param data: dictionary with data from flame
        """
        self._flame_batch_data = data

    def update_new_cut_info(self, record_in, record_out, handle_in, handle_out):
        """
        Updates the shot cut information based on segment cut information received from Flame.
        
        The frame information coming from Flame includes handles and is out frame exclusive, 
        meaning that the sequence 1,2,3,4,5 is denoted 1-6. 
        
        :param record_in: Record in parameter for a segment in Flame belonging to this shot
        :param record_out: Record out parameter for a segment in Flame belonging to this shot
        """
        
        # the cut in and cut out are reflected by the values stored in the conform
        # in Flame. These are sometimes defaulted to 10:00:00.00 so there may be some
        # large numbers here.
        cut_in = record_in 
        cut_out = record_out 
        
        # now, note that Flame is cut-out-exclusive, meaning that the out frame
        # is actually not the last frame played back but the frame after that.
        # in the Shotgun universe, we want last frame *inclusive* instead
        cut_out = cut_out - 1
        
        # now it is time to update the *SHOT* lengths. With Flame's collating,
        # a single shot may be made up of several *segments*. The cut information
        # we are getting from Flame is per segment. We need to "grow" the shot range
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

