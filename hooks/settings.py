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
import cgi
import re

HookBaseClass = sgtk.get_hook_baseclass()

class ExportSettings(HookBaseClass):
    """
    This hook controls the settings that flame will use when it exports the quicktimes 
    prior to uploading them to Shotgun. It also lets a user control where on disk temporary
    quicktime files will be located.
    """

    def get_ffmpeg_quicktime_encode_parameters(self):
        """
        Control how quicktimes are generated before being uploaded to Shotgun.
        These quicktimes are generated using ffmpeg version SVN-r17733.
        
        :returns: string of ffmpeg parameters which will be appended to the ffmpeg command line
        """
        
        # the default hook implements the H264 (High) preset that is shipped with 
        # the wiretap central subsystem. The following parameters have been extracted from
        # the preset xml file. For detailed information about the meaning of any of these 
        # parameters, see https://trac.ffmpeg.org/wiki/Encode/H.264
        #
        # NOTE! The version of ffmpeg that ships with wiretap central is FFmpeg version SVN-r17733
        # from 2009 and its parameters do not seem to be compatible with modern versions of ffmpeg.
        # Therefore, the sample code for example outlined here won't work:
        # https://support.shotgunsoftware.com/entries/26303513-Transcoding
        
        params = ""         
        params += "-threads 2 -vcodec libx264 -me_method umh -directpred 3 -coder ac -me_range 16 -g 250 "
        params += "-rc_eq 'blurCplx^(1-qComp)' -keyint_min 25 -sc_threshold 40 -i_qfactor 0.71428572 "
        params += "-b_qfactor 0.76923078 -b_strategy 1 -qcomp 0.6 -qmin 10 -qmax 51 -qdiff 4  -trellis 1 "
        params += "-subq 6 -partitions +parti8x8+parti4x4+partp8x8+partp4x4+partb8x8 -bidir_refine 1 "
        params += "-cmp 1 -flags2 fastpskip -flags2 dct8x8 -flags2 mixed_refs -flags2 wpred "
        params += "-refs 2 -deblockalpha 0 -deblockbeta 0 -bf 3 "
        
        # Quality parameter (see https://trac.ffmpeg.org/wiki/Encode/H.264#crf):
        # "The range of the quantizer scale is 0-51: where 0 is lossless, 23 is default, 
        # and 51 is worst possible. A lower value is a higher quality and a subjectively 
        # sane range is 18-28. Consider 18 to be visually lossless or nearly so: it should 
        # look the same or nearly the same as the input but it isn't technically lossless."
        #
        # Note: 15 is the highest quality preset available in the wiretap central export presets.
        #
        params += "-crf 15 " 
        
        return params
        

    def get_export_preset(self, shot_parent_template_field):
        """
        Generate flame export profile settings suitable for generating image sequences
        for all shots.
        
        :param shot_parent_template_field: The template field which contains the shot parent.
                                           Typically, this is Sequence.
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
      <namePattern>{VIDEO_NAME_PATTERN}</namePattern>
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
      <namePattern>{SEGMENT_CLIP_NAME_PATTERN}</namePattern>
      <version>
         <index>0</index>
         <padding>{VERSION_PADDING}</padding>
         <name>v&lt;version&gt;</name>
      </version>
      <batchSetup>
         <namePattern>{BATCH_NAME_PATTERN}/</namePattern>
         <exportNamePattern>{SHOT_CLIP_NAME_PATTERN}/</exportNamePattern>
      </batchSetup>
   </createOpenClip>
   <reImport>
      <namePattern />
   </reImport>
</preset>
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
        # exact entity type to use is passed into the hook via the the shot_parent_template_field parameter.
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
        
        # get the export template defs for all our templates
        # the definition is a string on the form 
        # 'sequences/{Sequence}/{Shot}/editorial/plates/{segment_name}_{Shot}.v{version}.{SEQ}.dpx'
        template_defs = {}
        template_defs["plate_template"] = self.parent.get_template("plate_template").definition
        template_defs["batch_template"] = self.parent.get_template("batch_template").definition        
        template_defs["shot_clip_template"] = self.parent.get_template("shot_clip_template").definition
        template_defs["segment_clip_template"] = self.parent.get_template("segment_clip_template").definition
        
        # perform substitutions
        self.parent.log_debug("Performing field substitutions")
        for t in template_defs:
            
            self.parent.log_debug("Toolkit: %s" % template_defs[t])
            
            template_defs[t] = template_defs[t].replace("{%s}" % shot_parent_template_field, "<name>")
            template_defs[t] = template_defs[t].replace("{Shot}", "<shot name>")
            template_defs[t] = template_defs[t].replace("{segment_name}", "<segment name>")
            template_defs[t] = template_defs[t].replace("{version}", "<version>")
            template_defs[t] = template_defs[t].replace("{SEQ}", "<frame>")
            
            # Now carry over the sequence token
            (head, ext) = os.path.splitext(template_defs[t])
            template_defs[t] = "%s<ext>" % head
            
            self.parent.log_debug("Flame:  %s" % template_defs[t])
        
        # now perform substitutions
        xml = xml.replace("{VIDEO_NAME_PATTERN}", cgi.escape(template_defs["plate_template"]))
        xml = xml.replace("{SEGMENT_CLIP_NAME_PATTERN}", cgi.escape(template_defs["segment_clip_template"]))
        xml = xml.replace("{BATCH_NAME_PATTERN}", cgi.escape(template_defs["batch_template"]))
        xml = xml.replace("{SHOT_CLIP_NAME_PATTERN}", cgi.escape(template_defs["shot_clip_template"]))

        # now adjust some parameters in the export xml based on the template
        # setup. 
        
        template = self.parent.get_template("plate_template")
        
        # First up is the padding for sequences:        
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
            
