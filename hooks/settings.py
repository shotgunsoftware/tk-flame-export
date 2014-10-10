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

HookBaseClass = sgtk.get_hook_baseclass()

class ExportSettings(HookBaseClass):
    """
    This hook controls the settings that flame will use when it exports the quicktimes 
    prior to uploading them to Shotgun. It also lets a user control where on disk temporary
    quicktime files will be located.
    """

    def resolve_sg_shot_structure(self, parent_name, shot_names, shot_task_template):
        """
        Resolve Shotgun Shot structure given export data from Flame.
        
        This default implementation assumes that the parent is a Sequence.
        
        """

        sg = self.parent.shotgun
        project = self.parent.context.project

        # first, ensure that a sequence exists in Shotgun with the parent name
        sg_parent = sg.find_one("Sequence", [["code", "is", parent_name], ["project", "is", project]]) 
        
        if not sg_parent:
            # Create a new sequence in Shotgun
                
            sg_parent = sg.create("Sequence", {"code": parent_name, 
                                               "description": "Created by the Shotgun Flame exporter.",
                                               "project": project})
            
        # now resolve all the shots. Shots that don't already exists are created.
        shots = {}
        for shot_name in shot_names:

            shot = sg.find_one("Shot", [["code", "is", shot_name], ["sg_sequence", "is", sg_parent]])
            if shot:
                # store it in our return data dict
                shots[shot_name] = {"created": False, "shotgun": shot}
            
            else:
                # Create a new shot in Shotgun
                
                # First see if we should assign a task template
                if shot_task_template:
                    # resolve task template
                    sg_task_template = sg.find_one("TaskTemplate", [["code", "is", shot_task_template]])
                    if not sg_task_template:
                        raise TankError("The task template '%s' does not exist in Shotgun!" % shot_task_template)
                else:
                    sg_task_template = None
                    
                shot = sg.create("Shot", {"code": shot_name, 
                                          "description": "Created by the Shotgun Flame exporter.",
                                          "sg_sequence": sg_parent,
                                          "task_template": sg_task_template,
                                          "project": project})
                
                shots[shot_name] = {"created": True, "shotgun": shot} 
            
        return shots



    def get_export_preset(self):
        """
        Generate flame export profile settings suitable for generating image sequences
        for all shots.
        
        :returns: path to export preset xml file
        """
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<preset version="4">
   <type>sequence</type>
   <comment>Creates shot directories with media, setups and clips for all shots in the sequence.
The generated media is 10-bit DPX and no audio.</comment>
   <sequence>
      <fileType>NONE</fileType>
      <namePattern />
      <includeVideo>True</includeVideo>
      <exportVideo>True</exportVideo>
      <videoMedia>
         <mediaFileType>image</mediaFileType>
         <commit>Original</commit>
         <flatten>NoChange</flatten>
         <exportHandles>True</exportHandles>
         <nbHandles>10</nbHandles>
      </videoMedia>
      <includeAudio>True</includeAudio>
      <exportAudio>False</exportAudio>
      <audioMedia>
         <mediaFileType>audio</mediaFileType>
         <commit>Original</commit>
         <flatten>NoChange</flatten>
         <exportHandles>True</exportHandles>
         <nbHandles>10</nbHandles>
      </audioMedia>
   </sequence>
   <video>
      <fileType>Dpx</fileType>
      <codec>923680</codec>
      <codecProfile />
      <namePattern>&lt;shot name&gt;/dpx/&lt;version name&gt;/&lt;shot name&gt;_&lt;segment name&gt;.&lt;version name&gt;.</namePattern>
      <compressionQuality>50</compressionQuality>
      <transferCharacteristic>2</transferCharacteristic>
      <colorimetricSpecification>4</colorimetricSpecification>
      <publishLinked>True</publishLinked>
      <foregroundPublish>False</foregroundPublish>
      <overwriteWithVersions>False</overwriteWithVersions>
      <resize>
         <resizeType>fit</resizeType>
         <resizeFilter>lanczos</resizeFilter>
         <width>0</width>
         <height>0</height>
         <bitsPerChannel>10</bitsPerChannel>
         <numChannels>3</numChannels>
         <floatingPoint>False</floatingPoint>
         <bigEndian>True</bigEndian>
         <pixelRatio>1</pixelRatio>
         <scanFormat>P</scanFormat>
      </resize>
   </video>
   <name>
      <framePadding>{FRAME_PADDING}</framePadding>
      <startFrame>0</startFrame>
      <useTimecode>False</useTimecode>
   </name>
   <createOpenClip>
      <namePattern>&lt;shot name&gt;/flame/sources/&lt;segment name&gt;</namePattern>
      <version>
         <index>0</index>
         <padding>{VERSION_PADDING}</padding>
         <name>v&lt;version&gt;</name>
      </version>
      <batchSetup>
         <namePattern>&lt;shot name&gt;/flame/batch/&lt;shot name&gt;_&lt;version name&gt;</namePattern>
         <exportNamePattern>&lt;shot name&gt;/flame/&lt;shot name&gt;</exportNamePattern>
      </batchSetup>
   </createOpenClip>
   <reImport>
      <namePattern />
   </reImport>
</preset>
        """
        
        # get the export template for the plates
        template = self.parent.get_template("plate_template")

        # now adjust some parameters in the export xml based on the template
        # setup. First up is the padding for sequences:        
        sequence_key = template.keys["SEQ"]
        # the format spec is something like "04"
        format_spec = sequence_key.format_spec
        if format_spec.startswith("0"):
            # strip off leading zeroes
            format_spec = format_spec[1:]
        xml = xml.replace("{FRAME_PADDING}", format_spec)
        
        self.parent.log_debug("Flame preset generation: Setting frame padding to %s based on "
                              "SEQ token in template %s" % (format_spec, template))

        # also align the padding for versions with the definition in the version template
        version_key = template.keys["version"]
        # the format spec is something like "03"
        format_spec = version_key.format_spec
        if format_spec.startswith("0"):
            # strip off leading zeroes
            format_spec = format_spec[1:]        
        xml = xml.replace("{VERSION_PADDING}", format_spec)
        
        self.parent.log_debug("Flame preset generation: Setting version padding to %s based on "
                              "version token in template %s" % (format_spec, template))
        
        # write it to disk
        preset_path = self._write_content_to_file(xml, "export_preset.xml")
        
        return preset_path






    ###############################################################################################
    # helper methods and internals
    
    def _write_content_to_file(self, content, file_name):
        """
        Helper method. Writes content to file and returns the path.
        The content will be written to the app specific cache location 
        on disk, organized by app instance name. The rationale is that 
        each app instance holds its own configuration, and the configuration
        generates one set of unique xml files.
        
        :param content: Data to write to the file
        :param file_name: The name of the file to create
        :returns: path to the created file
        """
        # determine location
        file_path = os.path.join(self.parent.cache_location, self.parent.instance_name, file_name)
        folder = os.path.dirname(file_path)

        # create folders
        if not os.path.exists(folder):
            old_umask = os.umask(0)
            os.makedirs(folder, 0777)
            os.umask(old_umask)
        
        # write data
        fh = open(file_path, "wt")
        fh.write(content)
        fh.close()
        
        self.parent.log_debug("Wrote temporary file '%s'" % file_path)
        return file_path
            
        
        
        