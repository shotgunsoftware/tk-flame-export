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
import pprint
import math
import uuid
from sgtk import TankError
import os
import re

from .shot_metadata import ShotMetadata

class ShotgunSubmitter(object):
    """
    Helper class with methods to submit publishes and versions to Shotgun
    """
    
    # constants
    SHOTGUN_QUICKTIME_MIN_WIDTH = 720
    SHOTGUN_DEPARTMENT = "Flame"
    
    def __init__(self):
        """
        Constructor
        """
        self._app = sgtk.platform.current_bundle()
        
        # get some app settings configuring how shots are parented
        self._shot_parent_entity_type = self._app.get_setting("shot_parent_entity_type")
        self._shot_parent_link_field = self._app.get_setting("shot_parent_link_field")

    def create_shotgun_structure(self, parent_name, shot_names):
        """
        Create a scaffold in Shotgun and on disk to represent Shots.
        This method will
        
        - Create sequences and shots in shotgun if they don't already exist
        - Create folders on disk for new shots
        - Compute tk contexts for all shots
        
        Returns a dictionary of sequences. Each sequence name contains a dictu
        
        { "Sequence_x": { "Shot_x_1":  ShotMetadata,
                          "Shot_x_2":  ShotMetadata,
                          "Shot_x_2":  ShotMetadata }}
        
        :returns: dict with shot data        
        """
        data = {}
        
        self._app.log_debug("Preparing export structure for %s %s and shots %s" % (self._shot_parent_entity_type, 
                                                                                   parent_name, 
                                                                                   shot_names))
        self._app.engine.show_busy("Preparing Shotgun...", "Preparing Shots for export...")
        
        try:
            # find and create objects in shotgun
            shot_metadata_list = self._resolve_sg_shot_structure(parent_name, shot_names)
            
            # set up metadata objects grouped by sequence in our data structure
            data[parent_name] = {}
            
            for shot_metadata in shot_metadata_list:
                data[parent_name][shot_metadata.name] = shot_metadata
            
            # now get the metadata objects for all shots that were created by the folder creation
            new_shot_metadata = [x for x in data[parent_name].values() if x.created_this_session]
            
            # run folder creation for our newly created shots
            for (idx, shot_metadata) in enumerate(new_shot_metadata):
                # this is a new shot
                msg = "%s/%s: Creating folders for Shot %s..." % (idx+1, len(new_shot_metadata), shot_metadata.name)
                self._app.engine.show_busy("Preparing Shotgun...", msg)
                self._app.sgtk.create_filesystem_structure("Shot", shot_metadata.shotgun_id, engine="tk-flame")
            
            # establish a context for all objects
            self._app.engine.show_busy("Preparing Shotgun...", "Resolving Shot contexts...")
            for shot_metadata in data[parent_name].values():
                shot_metadata.context = self._app.sgtk.context_from_entity("Shot", shot_metadata.shotgun_id)
            
        finally:
            # kill progress indicator
            self._app.engine.clear_busy()
        
        return data

    def _resolve_sg_shot_structure(self, parent_name, shot_names):
        """
        Ensures that Shots exists in Shotgun. Will automatically create
        Shots and Shot parents (e.g. sequences) if necessary and assign
        task templates. Returns a dictionary with Shot metadata
        
        :param parent_name: Name of the shot parent (usually this is the sequence)
        :param shot_names: List of shot names
        :returns: List of ShotMetadata objects  
        """
        # get some configuration settings first
        shot_task_template = self._app.get_setting("task_template")
        if shot_task_template == "":
            shot_task_template = None

        parent_task_template = self._app.get_setting("shot_parent_task_template")
        if parent_task_template == "":
            parent_task_template = None

        # handy shorthand
        project = self._app.context.project

        # --------------------------------------------------------------------------------------------
        # first, ensure that a parent exists in Shotgun with the parent name
        self._app.engine.show_busy("Preparing Shotgun...", 
                                   "Locating %s %s..." % (self._shot_parent_entity_type, parent_name))
        
        sg_parent = self._app.shotgun.find_one(self._shot_parent_entity_type, 
                                               [["code", "is", parent_name], ["project", "is", project]]) 
        
        if not sg_parent:
            # Create a new parent object in Shotgun
            
            # First see if we should assign a task template
            if parent_task_template:
                # resolve task template
                self._app.engine.show_busy("Preparing Shotgun...", "Loading task template...")
                sg_task_template = self._app.shotgun.find_one("TaskTemplate", [["code", "is", parent_task_template]])
                if not sg_task_template:
                    raise TankError("The task template '%s' does not exist in Shotgun!" % parent_task_template)
            else:
                sg_task_template = None

            self._app.engine.show_busy("Preparing Shotgun...", 
                                       "Creating %s %s..." % (self._shot_parent_entity_type, parent_name))
            
            sg_parent = self._app.shotgun.create(self._shot_parent_entity_type, 
                                                 {"code": parent_name, 
                                                  "task_template": sg_task_template,
                                                  "description": "Created by the Shotgun Flame exporter.",
                                                  "project": project})
  
        
        # --------------------------------------------------------------------------------------------
        # First locate a task template for shots
        if shot_task_template:
            # resolve task template
            self._app.engine.show_busy("Preparing Shotgun...", "Loading task template...")
            sg_task_template = self._app.shotgun.find_one("TaskTemplate", [["code", "is", shot_task_template]])
            if not sg_task_template:
                raise TankError("The task template '%s' does not exist in Shotgun!" % shot_task_template)
        else:
            sg_task_template = None
  
        # now attempt to retrieve metadata for all shots. The shots that are not found are then created.
        self._app.engine.show_busy("Preparing Shotgun...", "Loading Shot data...")
        
        sg_shots = self._app.shotgun.find_one("Shot", 
                                              [["code", "in", shot_names], 
                                               [self._shot_parent_link_field, "is", sg_parent]],
                                              ["code", "sg_cut_in", "sg_cut_out", "sg_cut_order"])
        
        # key it by name. Check for duplicates.
        sg_shot_dict = {}
        for sg_shot in sg_shots:
            shot_name = sg_shot["code"]
            if shot_name in sg_shots:
                raise TankError("There are several Shots linked to %s %s and named '%s' "
                                "in Shotgun!" % (self._shot_parent_entity_type, parent_name, shot_name))
            sg_shot_dict[shot_name] = sg_shot
        
        # start gathering metadata objects to represent all required shots.
        # some of these shots will need to be created in Shotgun.
        final_shots_metadata = []
        
        # first create all shots that don't exist. Use a single batch call for speed.
        sg_batch_data = []
        for shot_name in shot_names:
            if shot_name not in sg_shot_dict:
                # this shot does not yet exist in Shotgun
                batch = {"request_type": "create", 
                         "entity_type": "Shot", 
                         "data": {"code": shot_name, 
                                  "description": "Created by the Shotgun Flame exporter.",
                                  self._shot_parent_link_field: sg_parent,
                                  "task_template": sg_task_template,
                                  "project": project} }
                sg_batch_data.append(batch)
        
        if len(sg_batch_data) > 0:
            self._app.engine.show_busy("Preparing Shotgun...", "Creating new shots...")
            sg_batch_response = self._app.shotgun.batch(sg_batch_data)

            # for each new shot, create a metadata object
            for sg_data in sg_batch_response: 
                metadata = ShotMetadata()
                metadata.name = sg_data["code"]
                metadata.shotgun_id = sg_data["id"]
                metadata.parent_name = parent_name
                metadata.shotgun_parent = sg_parent
                metadata.created_this_session = True
                final_shots_metadata.append(metadata)
            
        # now add all existing shots to our return metadata structure        
        for shot_name in shot_names:
            if shot_name in sg_shot_dict:
                metadata = ShotMetadata()
                metadata.name = shot_name
                metadata.parent_name = parent_name
                metadata.shotgun_parent = sg_parent
                metadata.shotgun_id = sg_shot_dict[shot_name]["id"]
                metadata.shotgun_cut_in = sg_shot_dict[shot_name]["sg_cut_in"]
                metadata.shotgun_cut_out = sg_shot_dict[shot_name]["sg_cut_out"]
                final_shots_metadata.append(metadata)
            
        # all done!
        return final_shots_metadata

    def register_batch_publish(self, context, path, comments, version_number):
        """
        Creates a publish record in shotgun for a flame batch file.
        
        :param context: Context to associate the publish with
        :param path: Path to the batch file on disk
        :param comments: Details about the publish
        :param version_number: The version number to use
        :returns: Shotgun data for the created item
        """
        self._app.log_debug("Creating batch publish in Shotgun...")                
        publish_type = self._app.get_setting("batch_publish_type")
                                
        # put together a name for the publish. This should be on a form without a version
        # number, so that it can be used to group together publishes of the same kind, but
        # with different versions.
        # e.g. 'sequences/{Sequence}/{Shot}/editorial/flame/batch/{Shot}.v{version}.batch'
        batch_template = self._app.get_template("batch_template")
        fields = batch_template.get_fields(path)
        publish_name = fields.get("Shot")
            
        # now start assemble publish parameters
        args = {
            "tk": self._app.sgtk,
            "context": context,
            "comment": comments,
            "path": path,
            "name": publish_name,
            "version_number": version_number,
            "created_by": context.user,
            "task": context.task,
            "published_file_type": publish_type,
        }
        
        self._app.log_debug("Register publish in shotgun: %s" % str(args))        
        sg_publish_data = sgtk.util.register_publish(**args)
        self._app.log_debug("Register complete: %s" % sg_publish_data)
        return sg_publish_data
        
        
    def register_video_publish(self, context, path, comments, version_number, width, height, make_shot_thumb):        
        """
        Creates a publish record in shotgun for a flame batch file.
        
        :param context: Context to associate the publish with
        :param path: Flame-style path to the frame sequence
        :param comments: Details about the publish
        :param version_number: The version number to use
        :param width: Image width in pixels
        :param height: Image height in pixels
        :param make_shot_thumb: If set to True, the thumbnail that gets associated with the 
                                publish will also be pushed to the associated entity.
        :returns: Shotgun data for the created item
        """
        self._app.log_debug("Creating video publish in Shotgun...")
                                    
        # put together a name for the publish. This should be on a form without a version
        # number, so that it can be used to group together publishes of the same kind, but
        # with different versions. 
        # e.g. 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        # 
        # In order to determine this, loop over all the plate presets, find the matching profile
        # and use that
        publish_name = "unknown"
        publish_type = "Unknown"
        for preset in self._app.get_setting("plate_presets"):
            plate_template_name = preset["template"]
            template = self._app.get_template_by_name(plate_template_name)
            if template.validate(path):
                fields = template.get_fields(path)
                publish_name = "%s, %s" % (fields.get("Shot"), fields.get("segment_name"))
                publish_type = preset["publish_type"]
                break
        
        # now start assemble publish parameters
        args = {
            "tk": self._app.sgtk,
            "context": context,
            "comment": comments,
            "path": path,
            "name": publish_name,
            "version_number": version_number,
            "created_by": context.user,
            "task": context.task,
            "published_file_type": publish_type,
        }
        
        # now try to extract a thumbnail from the asset data stream.
        # we use the same mechanism that the quicktime generation is using - see
        # the quicktime code below for details:
        #
        input_cmd = "%s -n \"%s@CLIP\" -h %s -W %s -H %s -L" % (self._app.engine.get_read_frame_path(),
                                                                path,
                                                                "%s:Gateway" % self._app.engine.get_server_hostname(), 
                                                                width,
                                                                height)
        
        thumbnail_jpg = os.path.join(self._app.engine.get_backburner_tmp(), "tk_thumb_%s.jpg" % uuid.uuid4().hex)
        if os.system("%s > %s" % (input_cmd, thumbnail_jpg)) != 0:
            self._app.log_warning("Could not extract thumbnail! See error log for details.")
        else:
            self._app.log_debug("Wrote thumbnail %s" % thumbnail_jpg)
            # add the thumbnail to the publish generation
            args["thumbnail_path"] = thumbnail_jpg
        
        # check if the shot needs a thumbnail
        if make_shot_thumb:
            args["update_entity_thumbnail"] = True
        
        self._app.log_debug("Register publish in shotgun: %s" % str(args))        
        sg_publish_data = sgtk.util.register_publish(**args)
        self._app.log_debug("Register complete: %s" % sg_publish_data)
        
        if thumbnail_jpg:
            # try to clean up
            self.__clean_up_temp_file(thumbnail_jpg)
            
        return sg_publish_data
            
    def update_version_dependencies(self, version_id, sg_publish_data):
        """
        Updates the dependencies for a version in Shotgun.
        
        :param version_id: Shotgun id for version to update
        :param sg_publish_data: Dictionary with type/id keys to connect.
        """
        data = {}
        
        # link to the publish
        if sgtk.util.get_published_file_entity_type(self._app.sgtk) == "PublishedFile":
            # client is using published file entity
            data["published_files"] = [sg_publish_data]
        else:
            # client is using old "TankPublishedFile" entity
            data["tank_published_file"] = sg_publish_data
            
        self._app.log_debug("Updating dependencies for version %s: %s" % (version_id, data))
        self._app.shotgun.update("Version", version_id, data)
        self._app.log_debug("...version update complete")
    
    
    def create_version(self, context, path, user_comments, sg_publish_data, aspect_ratio):        
        """
        Create a version record in shotgun, generate a quicktime and upload it.
        
        This method will do the following:
        - Create a Shotgun version entity and populate as much metadata as possible
        - Generate a quicktime by streaming the asset data via wiretap into ffmepg.
          A h264 quicktime with shotgun-friendly settings are created, however the quicktime
          defaults are defined in the settings hook and can be controlled by the user.
        - Lastly, uploads the quicktime to Shotgun and then deletes it off disk.        
        
        :param context: The context for the shot that the submission is associated with, 
                        in serialized form.
        :param path: Path to frames, flame style path with [1234-1234] sequence marker.
        :param user_comments: Comments entered by the user at export start.
        :param sg_publish_data: Std shotgun dictionary (with type and id), representing the publish
                                in Shotgun that has been carried out for this asset.
        :param aspect_ratio: Aspect ratio of the images
        :returns: The created shotgun record
        """
        data = {"context": context, 
                "path": path,
                "user_comments": user_comments,
                "sg_publish_data": sg_publish_data,
                "aspect_ratio": aspect_ratio }
        
        return self.create_versions(data)[0]

    
    def create_versions(self, data):
        """
        Identical to create_version(), but instead creates multiple versions using a single
        batch call to Shotgun for performance.
        
        :param data: List of dictionaries. Each dictionary contains the same keys as the parameters
                     defined in create_version() above.
        :returns: A list of created Shotgun records
        """
        
        sg_batch_data = []
        
        self._app.log_debug("Preparing to create %s version(s) in Shotgun..." % len(data))
        
        for version_params in data:
            
            context = version_params["context"] 
            path = version_params["path"]
            user_comments = version_params["user_comments"]
            sg_publish_data = version_params["sg_publish_data"]
            aspect_ratio = version_params["aspect_ratio"]
        
            batch_item = {"request_type": "create",
                          "entity_type": "Version",
                          "data": {}}
            
            # let the version name be the main file name of the plate
            # /path/to/filename -> filename
            # /path/to/filename.ext -> filename
            # /path/to/filename.%04d.ext -> filename
            file_name = os.path.basename(path)
            version_name = os.path.splitext(os.path.splitext(file_name)[0])[0]
            batch_item["data"]["code"] = version_name
            
            batch_item["data"]["description"] = user_comments
            batch_item["data"]["project"] = context.project
            batch_item["data"]["entity"] = context.entity
            batch_item["data"]["created_by"] = context.user
            batch_item["data"]["user"] = context.user
            batch_item["data"]["sg_task"] = context.task
            
            # now figure out the frame numbers. For an initial shotgun export this is easy because we have
            # access to the export profile which defines the frame offset which maps actual frames on disk with
            # frames in the cut space inside of flame. However, for batch rendering, which is currently stateless,
            # this info is not available. It may be possible to extract it from the clip xml files, but for now,
            # lets keep it simple and look at the sequence file path to extract this data.
            #
            # flame sequence tokens are on the form "[1001-1100]"
            re_match = re.search("\[([0-9]+)-([0-9]+)\]\.", path)
            if not re_match:
                self._app.log_warning("No frame range information found in path '%s'. "
                                      "Will proceed with undefined frame range." % path)
            else:
                try:
                    (first_str, last_str) = re_match.groups()
                    # remove leading zeroes and convert
                    first_str = first_str.lstrip("0")
                    last_str = last_str.lstrip("0")
                    # handle the case when a frame number is zero
                    if first_str == "":
                        first_str = "0"
                    if last_str == "":
                        last_str = "0"
                    first_frame = int(first_str)
                    last_frame = int(last_str)
                
                except Exception, e:
                    self._app.log_warning("Could not extract frame data from path '%s'. "
                                          "Will proceed without frame data. Error reported: %s" % (path, e))
                else:
                    # add frame data to version metadata
                    batch_item["data"]["sg_first_frame"] = first_frame
                    batch_item["data"]["sg_last_frame"] = last_frame
                    batch_item["data"]["frame_count"] = last_frame - first_frame + 1
                    batch_item["data"]["frame_range"] = "%s-%s" % (first_frame, last_frame)
                    batch_item["data"]["sg_frames_have_slate"] = False
                    batch_item["data"]["sg_movie_has_slate"] = False
                    batch_item["data"]["sg_frames_aspect_ratio"] = aspect_ratio
                    batch_item["data"]["sg_movie_aspect_ratio"] = aspect_ratio
    
            # link to the publish
            if sg_publish_data:
                if sgtk.util.get_published_file_entity_type(self._app.sgtk) == "PublishedFile":
                    # client is using published file entity
                    batch_item["data"]["published_files"] = [sg_publish_data]
                else:
                    # client is using old "TankPublishedFile" entity
                    batch_item["data"]["tank_published_file"] = sg_publish_data
            
            # populate the path to frames with a path which is using %4d syntax
            batch_item["data"]["sg_path_to_frames"] = self.__get_tk_path_from_flame_plate_path(path)
            
            # This is used to find the latest Version from the same department.
            batch_item["data"]["sg_department"] = self.SHOTGUN_DEPARTMENT   
        
            sg_batch_data.append(batch_item)
            
            self._app.log_debug("Version data: %s" % pprint.pformat(batch_item))
        
        
        self._app.log_debug("Executing version create batch call...")
        sg_version_data = self._app.shotgun.batch("Version", sg_batch_data)
        self._app.log_debug("...dpne")        
            
        return sg_version_data


    def upload_quicktime(self, version_id, path, width, height):        
        """
        Generates a quicktime based on flame image data. Then uploads it to
        Shotgun.

        This method will generate a quicktime using ffmpeg. It tries to find
        the closest resolution to 720p (which is shotgun's recommended resolution)
        in order to make the quicktime size as small as possible. Once generated,
        the quicktime is uploaded to Shotgun and the local temp file is deleted.
        
        :param version_id: The id for the shotgun version to which we are uploading a quicktime.
        :param path: Path to frames, flame style path with [1234-1234] sequence marker.
        :param width: Image width in pixels
        :param height: Image height in pixels
        """
        self._app.log_debug("Starting to upload media to Shotgun. A quicktime will be generated.")
        self._app.log_debug("Source media: %s (%sx%s)" % (path, width, height))
        self._app.log_debug("Computing closest image resolution to %s..." % self.SHOTGUN_QUICKTIME_MIN_WIDTH)
        
        # now calculate the closest res to with 720px
        (scaled_down_width, scaled_down_height) = self.__calculate_aspect_ratio(self.SHOTGUN_QUICKTIME_MIN_WIDTH, 
                                                                                width, 
                                                                                height) 
        
        self._app.log_debug("The quicktime will be resolution %sx%s" % (scaled_down_width, scaled_down_height))
                
        self._app.log_debug("Start transcoding quicktime...")

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
        input_cmd = "%s -n \"%s@CLIP\" -h %s -W %s -H %s -L -N -1 -r" % (self._app.engine.get_read_frame_path(),
                                                                         path,
                                                                         "%s:Gateway" % self._app.engine.get_server_hostname(),
                                                                         scaled_down_width,
                                                                         scaled_down_height)

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
        #  QUICKTIME_OPTIONS   <-- quicktime codec options (comes from hook)
        #  /output/file.mov    <-- target file
        #
        
        # note: the -r framerate argument seems to confuse ffmpeg so I am omitting that
        # instead, quicktimes are generated at a default of 25fps.
        
        ffmpeg_cmd = "%s -f rawvideo -top -1 -pix_fmt rgb24 -s %sx%s -i - -y" % (self._app.engine.get_ffmpeg_path(),
                                                                                 scaled_down_width,
                                                                                 scaled_down_height)
                                                                                       
        # get quicktime settings
        ffmpeg_presets = self._app.execute_hook_method("settings_hook", "get_ffmpeg_quicktime_encode_parameters")
        # generate target file
        tmp_quicktime = os.path.join(self._app.engine.get_backburner_tmp(), "tk_flame_%s.mov" % uuid.uuid4().hex) 

        full_cmd = "%s | %s %s %s" % (input_cmd, ffmpeg_cmd, ffmpeg_presets, tmp_quicktime)
        
        self._app.log_debug("Full transcoding command line: %s" % full_cmd)
        self._app.log_debug("Being quicktime generation...")
        if os.system(full_cmd) != 0:
            raise TankError("Could not transcode media. See error log for details.")
        self._app.log_debug("Quicktime successfully created!")
        self._app.log_debug("File size is %s bytes." % os.path.getsize(tmp_quicktime))
        
        # upload quicktime to Shotgun
        self._app.log_debug("Begin upload of quicktime to shotgun...")
        self._app.shotgun.upload("Version", version_id, tmp_quicktime, "sg_uploaded_movie")
        self._app.log_debug("...upload complete!")
        
        # clean up
        self.__clean_up_temp_file(tmp_quicktime)
    
    
    
    def __calculate_aspect_ratio(self, target_width, width, height):
        """
        Brute force calculation of aspect ratio.
        Finds the closest match to a target with resolution. If an absolute match is not found,
        the algorithm will try higher resolutions until it hits the original resolution which is
        returned in case no integer match is found.
        
        For example: Trying to scale the resolution 960x550 as close as possible to 720 will generate 768x440 
        
        :param target_width: The desired width
        :param width: The current width
        :param height: The current height
        :returns: int tuple, e.g. (768, 440)
        """
    
        if width <= target_width:
            # input res is lower than desired, so return directly
            return (width, height)
    
        # calculate initial values
        aspect_ratio = float(width)/float(target_width)
        new_height = 0
        new_width = 0
    
        # loop until an integer match is found both for width and height
        while new_height < height and new_width < width:
            
            # calculate our new values
            new_height = float(height)/aspect_ratio
            new_width = float(width)/aspect_ratio
    
            if new_height.is_integer() and new_width.is_integer():
                # both width and height is an integer! Done!
                return (int(new_width), int(new_height))
    
            if not new_height.is_integer():
                # height is not whole. adjust the height up to the next whole pixel
                # and try again. Note that if the current height is very close to 
                # a whole pixel, increment by one to avoid rounding errors.
                diff = new_height - math.trunc(new_height)
                if diff > 0.999:
                    # this is to avoid the case where there is a rounding error
                    # and math.ceil(x) == x which means we get stuck in a loop
                    new_height += 1
                # recalculate the aspect ratio
                aspect_ratio = float(height) / float(math.ceil(new_height))
    
            elif not new_width.is_integer():
                # width is not whole. adjust the width up to the next whole pixel
                # and try again. Note that if the current width is very close to 
                # a whole pixel, increment by one to avoid rounding errors.
                diff = new_width - math.trunc(new_width)
                if diff > 0.999:
                    # this is to avoid the case where there is a rounding error
                    # and math.ceil(x) == x which means we get stuck in a loop
                    new_width += 1
                # recalculate the aspect ratio
                aspect_ratio = float(width) / float(math.ceil(new_width))
    
        return (width, height)



    def __get_tk_path_from_flame_plate_path(self, flame_path):
        """
        Given a xxx.[1234-1234].exr style flame plate path,
        return the equivalent, normalized tk path, e.g. xxx.%04d.exr
        
        :param flame_path: flame style plate path (must match the plate template)
        :returns: tk equivalent
        """
        template = self._app.sgtk.template_from_path(flame_path)
        fields = template.get_fields(flame_path)    
        fields["SEQ"] = "FORMAT: %d"
        return template.apply_fields(fields)        

    def __clean_up_temp_file(self, path):
        """
        Helper method which attemps to delete up a given temp file.
        
        :param path: Path to delete
        """
        try:
            os.remove(path)
            self._app.log_debug("Removed temporary file '%s'." % path)
        except Exception, e:
            self._app.log_warning("Could not remove temporary file '%s': %s" % (path, e))    
