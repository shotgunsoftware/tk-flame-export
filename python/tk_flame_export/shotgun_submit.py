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
import uuid
from sgtk import TankError
import os
import re

from .shot_metadata import ShotMetadata

class ShotgunSubmitter(object):
    """
    Helper class with methods to submit publishes and versions to Shotgun
    """
    
    def __init__(self):
        """
        Constructor
        """
        self._app = sgtk.platform.current_bundle()


    def resolve_sg_shot_structure(self, parent_name, shot_names):
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

        shot_parent_entity_type = self._app.get_setting("shot_parent_entity_type")
        shot_parent_link_field = self._app.get_setting("shot_parent_link_field")

        # handy shorthand
        project = self._app.context.project

        # first, ensure that a parent exists in Shotgun with the parent name
        sg_parent = self._app.shotgun.find_one(shot_parent_entity_type, 
                                               [["code", "is", parent_name], ["project", "is", project]]) 
        
        if not sg_parent:
            # Create a new parent object in Shotgun
            
            # First see if we should assign a task template
            if parent_task_template:
                # resolve task template
                sg_task_template = self._app.shotgun.find_one("TaskTemplate", [["code", "is", parent_task_template]])
                if not sg_task_template:
                    raise TankError("The task template '%s' does not exist in Shotgun!" % parent_task_template)
            else:
                sg_task_template = None
            
            sg_parent = self._app.shotgun.create(shot_parent_entity_type, 
                                                 {"code": parent_name, 
                                                  "task_template": sg_task_template,
                                                  "description": "Created by the Shotgun Flame exporter.",
                                                  "project": project})
  
        # now resolve all the shots. Shots that don't already exists are created.
        shots = []
        for shot_name in shot_names:

            shot = self._app.shotgun.find_one("Shot", 
                                              [["code", "is", shot_name], [shot_parent_link_field, "is", sg_parent]],
                                              ["sg_cut_in", "sg_cut_out", "sg_cut_order"])
            
            metadata = ShotMetadata()
            metadata.name = shot_name
            metadata.parent_name = parent_name
            metadata.shotgun_parent = sg_parent
            shots.append(metadata)
            
            if shot:
                # store it in our return data dict
                metadata.shotgun_id = shot["id"]
                metadata.shotgun_cut_in = shot["sg_cut_in"]
                metadata.shotgun_cut_out = shot["sg_cut_out"]
            
            else:
                # Create a new shot in Shotgun
                
                # First see if we should assign a task template
                if shot_task_template:
                    # resolve task template
                    sg_task_template = self._app.shotgun.find_one("TaskTemplate", [["code", "is", shot_task_template]])
                    if not sg_task_template:
                        raise TankError("The task template '%s' does not exist in Shotgun!" % shot_task_template)
                else:
                    sg_task_template = None
                    
                shot = self._app.shotgun.create("Shot", {"code": shot_name, 
                                                    "description": "Created by the Shotgun Flame exporter.",
                                                    shot_parent_link_field: sg_parent,
                                                    "task_template": sg_task_template,
                                                    "project": project})
                
                # store it in our return data dict
                metadata.created_this_session = True
                metadata.shotgun_id = shot["id"]
            
        return shots


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
        publish_type = self._app.get_setting("plate_publish_type")
                                    
        # put together a name for the publish. This should be on a form without a version
        # number, so that it can be used to group together publishes of the same kind, but
        # with different versions. 
        # e.g. 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        plate_template = self._app.get_template("plate_template")
        fields = plate_template.get_fields(path)            
        publish_name = "%s, %s" % (fields.get("Shot"), fields.get("segment_name"))
        
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
        
        thumbnail_jpg = None
        
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
            
    def create_version(self, context, path, user_comments, sg_publish_data, width, height, aspect_ratio):        
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
        :param width: Image width in pixels
        :param height: Image height in pixels
        :param aspect_ratio: Aspect ratio of the images
        :returns: The created shotgun record
        """
        
        # note / todo: there doesn't seem to be any way to downscale the quicktime
        # as it is being generated/streamed out of wiretap and encoded by ffmpeg.
        # ideally we would like to downrez it to height 720px prior to uploading
        # according to the Shotgun transcoding guidelines (and to optimize bandwidth)        

        self._app.log_debug("Begin version processing for %s..." % path)

        data = {}
        
        # let the version name be the main file name of the plate
        # /path/to/filename -> filename
        # /path/to/filename.ext -> filename
        # /path/to/filename.%04d.ext -> filename
        file_name = os.path.basename(path)
        version_name = os.path.splitext(os.path.splitext(file_name)[0])[0]
        data["code"] = version_name
        
        data["description"] = user_comments
        data["project"] = context.project
        data["entity"] = context.entity
        data["created_by"] = context.user
        data["user"] = context.user
        data["sg_task"] = context.task
        
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
                data["sg_first_frame"] = first_frame
                data["sg_last_frame"] = last_frame
                data["frame_count"] = last_frame - first_frame + 1
                data["frame_range"] = "%s-%s" % (first_frame, last_frame)
                data["sg_frames_have_slate"] = False
                data["sg_movie_has_slate"] = False
                data["sg_frames_aspect_ratio"] = aspect_ratio
                data["sg_movie_aspect_ratio"] = aspect_ratio

        # link to the publish
        if sgtk.util.get_published_file_entity_type(self._app.sgtk) == "PublishedFile":
            # client is using published file entity
            data["published_files"] = [sg_publish_data]
        else:
            # client is using old "TankPublishedFile" entity
            data["tank_published_file"] = sg_publish_data
        
        # populate the path to frames with a path which is using %4d syntax
        data["sg_path_to_frames"] = self.__get_tk_path_from_flame_plate_path(path)
        
        # This is used to find the latest Version from the same department.
        # todo: make this configurable?
        data["sg_department"] = "Flame"        
        
        sg_version_data = self._app.shotgun.create("Version", data)
        self._app.log_debug("Created a version in Shotgun: %s" % sg_version_data)        
        
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
                                                                         width,
                                                                         height)

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
        #  -r 25               <-- need to tell ffmpeg what the fps is 
        #  QUICKTIME_OPTIONS   <-- quicktime codec options (comes from hook)
        #  /output/file.mov    <-- target file
        #
        
        # note: the -r framerate argument seems to confuse ffmpeg so I am omitting that
        # instead, quicktimes are generated at 25fps.
        
        ffmpeg_cmd = "%s -f rawvideo -top -1 -pix_fmt rgb24 -s %sx%s -i - -y" % (self._app.engine.get_ffmpeg_path(),
                                                                                 width,
                                                                                 height)
                                                                                       
        # get quicktime settings
        ffmpeg_presets = self._app.execute_hook_method("settings_hook", "get_ffmpeg_quicktime_encode_parameters")
        # generate target file
        tmp_quicktime = os.path.join(self._app.engine.get_backburner_tmp(), "tk_flame_%s.mov" % uuid.uuid4().hex) 

        full_cmd = "%s | %s %s %s" % (input_cmd, ffmpeg_cmd, ffmpeg_presets, tmp_quicktime)
        
        self._app.log_debug("Transcoding command line: %s" % full_cmd)
        
        if os.system(full_cmd) != 0:
            raise TankError("Could not transcode media. See error log for details.")
        
        self._app.log_debug("Quicktime successfully created!")
        self._app.log_debug("File size is %s bytes." % os.path.getsize(tmp_quicktime))
        
        # upload quicktime to Shotgun
        self._app.log_debug("Begin upload of quicktime to shotgun...")
        self._app.shotgun.upload("Version", sg_version_data["id"], tmp_quicktime, "sg_uploaded_movie")
        self._app.log_debug("Upload complete!")
        
        # clean up
        self.__clean_up_temp_file(tmp_quicktime)
    
        return sg_version_data

    def __get_tk_path_from_flame_plate_path(self, flame_path):
        """
        Given a xxx.[1234-1234].exr style flame plate path,
        return the equivalent, normalized tk path, e.g. xxx.%04d.exr
        
        :param flame_path: flame style plate path (must match the plate template)
        :returns: tk equivalent
        """
        plate_template = self._app.get_template("plate_template")
        fields = plate_template.get_fields(flame_path)    
        fields["SEQ"] = "FORMAT: %d"
        return plate_template.apply_fields(fields)        


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
