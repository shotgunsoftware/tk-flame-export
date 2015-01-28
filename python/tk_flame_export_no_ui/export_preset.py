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
from sgtk import TankError
import cgi
import sys
import os
        
class ExportPreset(object):
    """
    Wrapper class that handles the Flame export preset.
    
    This class contains the key method get_xml_path(), which will return a path
    on disk where an xml export preset is located.
    
    This preset is combined by loading various sources - some of the main scaffold
    xml is in this file, the export dpx plate presets are loaded in via a hook, paths
    are converted from toolkit templates and resolved.
    """

    def __init__(self):
        """
        Constructor
        """
        self._app = sgtk.platform.current_bundle()

    def get_xml_path(self, video_preset):
        """
        Generate flame export profile settings suitable for generating image sequences
        for all shots.
        
        :param video_preset: The name of the video preset name that should be used.
        :returns: path to export preset xml file
        """
        
        resolved_flame_templates = self.__resolve_flame_templates(video_preset)
        
        # a note on xml file formats: 
        # Each major version of flame typically implements a particular 
        # version of the preset xml protocol. This is denoted by a preset version
        # number in the xml file. In order for the integration to run smoothly across
        # multiple versions of flame, flame ideally needs to be presented with a preset
        # which matches the current preset version. If you present an older version, a
        # warning dialog may pop up which is confusing to users. Therefore, make sure that
        # we always generate xmls with a matching preset version.   
        preset_version = self._app.engine.preset_version
        
        
        xml = """<?xml version="1.0" encoding="UTF-8"?>
            <preset version="%s">
               <type>sequence</type>
               <comment>Export profile for the Shotgun Flame export</comment>
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
            
               {VIDEO_EXPORT_PRESET}
               
               <name>
                  <framePadding>{FRAME_PADDING}</framePadding>
                  <startFrame>100</startFrame>
                  <useTimecode>False</useTimecode>
               </name>
               <createOpenClip>
                  <namePattern>{SEGMENT_CLIP_NAME_PATTERN}</namePattern>
                  <version>
                     <index>0</index>
                     <padding>{VERSION_PADDING}</padding>
                     <name>v&lt;version&gt;</name>
                  </version>
                  <batchSetup>
                     <namePattern>{BATCH_NAME_PATTERN}</namePattern>
                     <exportNamePattern>{SHOT_CLIP_NAME_PATTERN}</exportNamePattern>
                  </batchSetup>
               </createOpenClip>
               <reImport>
                  <namePattern />
               </reImport>
            </preset>
        """ % preset_version
        
        # merge in the video preset via a hook
        video_name_pattern = cgi.escape(resolved_flame_templates["plate_template"])
        video_preset_xml = self._app.execute_hook_method("settings_hook", 
                                                         "get_video_preset", 
                                                         preset_name=video_preset, 
                                                         name_pattern=video_name_pattern, 
                                                         publish_linked=True)
        
        xml = xml.replace("{VIDEO_EXPORT_PRESET}", video_preset_xml)
        
        # now perform substitutions based on the resolved flame templates
        # make sure we escape any < and > before we add them to the xml
        xml = xml.replace("{SEGMENT_CLIP_NAME_PATTERN}", cgi.escape(resolved_flame_templates["segment_clip_template"]))
        xml = xml.replace("{BATCH_NAME_PATTERN}",        cgi.escape(resolved_flame_templates["batch_template"]))
        xml = xml.replace("{SHOT_CLIP_NAME_PATTERN}",    cgi.escape(resolved_flame_templates["shot_clip_template"]))

        # now adjust some parameters in the export xml based on the template setup. 
        template = self._app.get_plate_template_for_preset(video_preset)
        
        # First up is the padding for sequences:        
        sequence_key = template.keys["SEQ"]
        # the format spec is something like "04"
        format_spec = sequence_key.format_spec
        if format_spec.startswith("0"):
            # strip off leading zeroes
            format_spec = format_spec[1:]
        xml = xml.replace("{FRAME_PADDING}", format_spec)
        
        self._app.log_debug("Flame preset generation: Setting frame padding to %s based on "
                            "SEQ token in template %s" % (format_spec, template))

        # also align the padding for versions with the definition in the version template
        version_key = template.keys["version"]
        # the format spec is something like "03"
        format_spec = version_key.format_spec
        if format_spec.startswith("0"):
            # strip off leading zeroes
            format_spec = format_spec[1:]        
        xml = xml.replace("{VERSION_PADDING}", format_spec)
        
        self._app.log_debug("Flame preset generation: Setting version padding to %s based on "
                            "version token in template %s" % (format_spec, template))
        
        # write it to disk
        preset_path = self.__write_content_to_file(xml, "export_preset.xml")
        
        return preset_path



    ###############################################################################################
    # helper methods and internals
    
    def __write_content_to_file(self, content, file_name):
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
        file_path = os.path.join(self._app.cache_location, self._app.instance_name, file_name)
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
        
        self._app.log_debug("Wrote temporary file '%s'" % file_path)
        return file_path

    def __resolve_flame_templates(self, video_preset):
        """
        Convert the toolkit templates defined in the app settings to 
        Flame equivalents.
        
        :returns: Dictionary of flame template definition strings, keyed by
                  the same names as are being used for the templates in the app settings.
        """
        # now we need to take our toolkit templates and inject them into the xml template
        # definition that we are about to send to Flame.
        #
        # typically, our template defs will look something like this:
        # plate:        'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        # batch:        'sequences/{Sequence}/{Shot}/editorial/flame/batch/{Shot}.v{version}.batch'
        # segment_clip: 'sequences/{Sequence}/{Shot}/editorial/flame/sources/{segment_name}.clip'
        # shot_clip:    'sequences/{Sequence}/{Shot}/editorial/flame/{Shot}.clip'
        #
        # {Sequence} may be {Scene} or {CustomEntityXX} according to the configuration and the 
        # exact entity type to use is passed into the hook via the the shot_parent_entity_type setting.
        #
        # The flame export root is set to correspond to the toolkit project, meaning that both the 
        # flame and toolkit templates share the same root point.
        #
        # The following replacements will be made to convert the toolkit template into Flame equivalents:
        # 
        # {Sequence}     ==> <name> (Note: May be {Scene} or {CustomEntityXX} according to the configuration)
        # {Shot}         ==> <shot name>
        # {segment_name} ==> <segment name>
        # {version}      ==> <version>
        # {SEQ}          ==> <frame>
        # 
        # and the special one <ext> which corresponds to the last part of the template. In the examples above:
        # {segment_name}_{Shot}.v{version}.{SEQ}.dpx : <ext> is '.dpx' 
        # {Shot}.v{version}.batch : <ext> is '.batch'
        # etc.
        #
        # example substitution:
        #
        # Toolkit: 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        #
        # Flame:   'sequences/<name>/<shot name>/editorial/plates/<segment name>_<shot name>.v<version>.<frame><ext>'
        #
        #
        shot_parent_entity_type = self._app.get_setting("shot_parent_entity_type")
        
        # get the plate template given the preset name
        plate_template = self._app.get_plate_template_for_preset(video_preset)
        
        # get the export template defs for all our templates
        # the definition is a string on the form 
        # 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        template_defs = {}
        template_defs["plate_template"] = plate_template.definition
        template_defs["batch_template"] = self._app.get_template("batch_template").definition        
        template_defs["shot_clip_template"] = self._app.get_template("shot_clip_template").definition
        template_defs["segment_clip_template"] = self._app.get_template("segment_clip_template").definition
        
        # perform substitutions
        self._app.log_debug("Performing Toolkit -> Flame template field substitutions:")
        for t in template_defs:
            
            self._app.log_debug("Toolkit: %s" % template_defs[t])
            
            template_defs[t] = template_defs[t].replace("{%s}" % shot_parent_entity_type, "<name>")
            template_defs[t] = template_defs[t].replace("{Shot}", "<shot name>")
            template_defs[t] = template_defs[t].replace("{segment_name}", "<segment name>")
            template_defs[t] = template_defs[t].replace("{version}", "<version>")
            
            template_defs[t] = template_defs[t].replace("{SEQ}", "<frame>")
            
            template_defs[t] = template_defs[t].replace("{YYYY}", "<YYYY>")
            template_defs[t] = template_defs[t].replace("{MM}", "<MM>")
            template_defs[t] = template_defs[t].replace("{DD}", "<DD>")
            template_defs[t] = template_defs[t].replace("{hh}", "<hh>")
            template_defs[t] = template_defs[t].replace("{mm}", "<mm>")
            template_defs[t] = template_defs[t].replace("{ss}", "<ss>")
            template_defs[t] = template_defs[t].replace("{width}", "<width>")
            template_defs[t] = template_defs[t].replace("{height}", "<height>")
                        
            # Now carry over the sequence token
            (head, ext) = os.path.splitext(template_defs[t])
            template_defs[t] = "%s<ext>" % head                        
            
            self._app.log_debug("Flame:  %s" % template_defs[t])
        
        return template_defs

