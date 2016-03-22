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
import sgtk
from sgtk import TankError


class Segment(object):
    """
    Represents a timeline segment in flame.

    Each timeline segment is parented under a shot.
    """
    def __init__(self, parent, name):
        """
        Constructor
        """
        self._app = sgtk.platform.current_bundle()

        self._shot = parent
        self._name = name
        self._flame_data = None

        # associated shotgun version
        self._shotgun_version_id = None

    def __repr__(self):
        return "<Segment %s, %s>" % (self._name, self._shot)

    @property
    def shot(self):
        """
        Returns the shot that this segment belongs to
        """
        return self._shot

    @property
    def name(self):
        """
        Returns the name of the sequence
        """
        return self._name

    @property
    def has_shotgun_version(self):
        """
        Returns true if a Shotgun version exists for the render associated with this segment.
        If a Shotgun version exists, it is implied that a render also exists.
        """
        return self._shotgun_version_id is not None

    @property
    def shotgun_version_id(self):
        """
        Returns the Shotgun id for the version associated with this segment, if there is one.
        """
        if not self.has_shotgun_version:
            raise TankError("Cannot get Shotgun version id for segment - no version associated!")
        return self._shotgun_version_id

    @property
    def has_render_export(self):
        """
        Returns true if a render export is associated with this segment, false if not.

        It is possible that an export doesn't have a render file exported if Flame for example
        prompts the user, asking her/him if they want to override an existing file and they
        select 'no'
        """
        return self._flame_data is not None

    @property
    def render_version_number(self):
        """
        Return the version number associated with the render file
        """
        if not self.has_render_export:
            raise TankError("Cannot get render path for segment - no video metadata found!")

        return int(self._flame_data["versionNumber"])

    @property
    def render_path(self):
        """
        Return the export render path for this segment
        """
        if not self.has_render_export:
            raise TankError("Cannot get render path for segment - no video metadata found!")

        return os.path.join(
            self._flame_data.get("destinationPath"),
            self._flame_data.get("resolvedPath")
        )

    @property
    def render_aspect_ratio(self):
        """
        Return the aspect ratio associated with the render file
        """
        if not self.has_render_export:
            raise TankError("Cannot get aspect ratio for segment - no video metadata found!")

        return self._flame_data["aspectRatio"]

    @property
    def backburner_job_id(self):
        """
        Return the backburner job id associated with this segment or None if not defined.
        """
        backburner_id = None
        if self._flame_data.get("isBackground"):
            backburner_id = self._flame_data.get("backgroundJobId")
        return backburner_id

    @property
    def render_width(self):
        """
        Returns the width of the flame render
        """
        if not self.has_render_export:
            raise TankError("Cannot get width for segment - no video metadata found!")

        return self._flame_data["width"]

    @property
    def render_fps(self):
        """
        Returns the width of the flame render
        """
        if not self.has_render_export:
            raise TankError("Cannot get fps for segment - no video metadata found!")

        return self._flame_data["fps"]

    @property
    def render_height(self):
        """
        Returns the height of the flame render
        """
        if not self.has_render_export:
            raise TankError("Cannot get height for segment - no video metadata found!")

        return self._flame_data["height"]

    @property
    def flame_track_id(self):
        """
        Returns the track id in flame, as an int
        """
        if not self.has_render_export:
            raise TankError("Cannot get track id for segment - no video metadata found!")

        # get track id as a three zero padded str, e.g. "002"
        track_id_str = self._flame_data["track"]
        return int(track_id_str)

    @property
    def edit_in_frame(self):
        """
        Returns the in frame for the edit point
        This denotes where this segment sits in the sequence based timeline.
        """
        if not self.has_render_export:
            raise TankError("Cannot get in frame for segment - no video metadata found!")

        return self._flame_data["recordIn"]

    @property
    def edit_out_frame(self):
        """
        Returns the out frame for the edit point.
        This denotes where this segment sits in the sequence based timeline.
        """
        if not self.has_render_export:
            raise TankError("Cannot get out frame for segment - no video metadata found!")

        return self._flame_data["recordOut"]

    @property
    def cut_in_frame(self):
        """
        Returns the in frame within the segment.
        This denotes at which frame playback of the segment should start within the
        local media associated with the segment.

        Note that since flame normalizes all sequences as part of its export,
        this value does not correspond to the value found in the original
        sequence data in flame.
        """
        if not self.has_render_export:
            raise TankError("Cannot get in frame for segment - no video metadata found!")

        return self._flame_data["handleIn"] + 1

    @property
    def cut_out_frame(self):
        """
        Returns the out frame within the segment.
        This denotes at which frame playback of the segment should stop within the
        local media associated with the segment.

        Note that since flame normalizes all sequences as part of its export,
        this value does not correspond to the value found in the original
        sequence data in flame.
        """
        if not self.has_render_export:
            raise TankError("Cannot get out frame for segment - no video metadata found!")

        clip_duration = self.edit_out_frame - self.edit_in_frame + 1
        return self._flame_data["handleIn"] + clip_duration

    def set_flame_data(self, flame_data):
        """
        Specify the flame hook data dictionary for this segment

        :param flame_data: dictionary with data from flame
        """
        self._flame_data = flame_data

    def set_shotgun_version_id(self, version_id):
        """
        Specifies the shotgun version id assocaited with this segment
        :param version_id: version id as int
        """
        self._shotgun_version_id = version_id

