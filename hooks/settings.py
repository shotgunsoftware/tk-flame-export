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
import os
import cgi

HookBaseClass = sgtk.get_hook_baseclass()

class ExportSettings(HookBaseClass):
    """
    This hook controls the settings that flame will use when it exports plates and generates 
    quicktimes prior to uploading them to Shotgun.
    """

    def get_video_preset(self, preset_name, name_pattern, publish_linked):
        """
        Returns a chunk of video xml export profile given a preset name.
        This chunk of XML will be joined into a larger structure which defines
        the entire set of export options. The app will then pass this full preset
        to flame for file generation.
        
        The preset name should correspond to one of the presets defined in the app
        config - for each of these presets, this hook needs to implement logic to 
        handle that preset. 
        
        Certain fields should be populated with particular data from the system.
        These 'dynamic fields' will get values via the input parameters of this method.
        
        :param preset_name: The name of the export preset that the user has selected in the 
                            export UI dialog.
        :param name_pattern: Data to inject into the <name_pattern> tag in the xml structure.
        :param publish_linked: Data to inject into the <publishLinked> tag in the xml structure.
        
        :returns: the <video> xml section of a flame export.
        """ 
        
        if preset_name == "10 bit DPX":
            xml = """
                   <video>
                      <fileType>Dpx</fileType>
                      <codec>923680</codec>
                      <codecProfile />
                      <namePattern>{VIDEO_NAME_PATTERN}</namePattern>
                      <compressionQuality>50</compressionQuality>
                      <transferCharacteristic>2</transferCharacteristic>
                      <colorimetricSpecification>4</colorimetricSpecification>
                      <publishLinked>{PUBLISH_LINKED}</publishLinked>
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
                """        
            
        elif preset_name == "16 bit OpenEXR":
            xml = """
                   <video>
                      <fileType>OpenEXR</fileType>
                      <codec>596088</codec>
                      <codecProfile />
                      <namePattern>{VIDEO_NAME_PATTERN}</namePattern>
                      <compressionQuality>50</compressionQuality>
                      <transferCharacteristic>2</transferCharacteristic>
                      <colorimetricSpecification>4</colorimetricSpecification>
                      <publishLinked>{PUBLISH_LINKED}</publishLinked>
                      <foregroundPublish>False</foregroundPublish>
                      <overwriteWithVersions>False</overwriteWithVersions>
                      <resize>
                         <resizeType>fit</resizeType>
                         <resizeFilter>lanczos</resizeFilter>
                         <width>0</width>
                         <height>0</height>
                         <bitsPerChannel>16</bitsPerChannel>
                         <numChannels>3</numChannels>
                         <floatingPoint>True</floatingPoint>
                         <bigEndian>False</bigEndian>
                         <pixelRatio>1</pixelRatio>
                         <scanFormat>P</scanFormat>
                      </resize>
                   </video>
                """
                
        else:
            raise TankError("Unknown video export preset '%s'!" % preset_name)
        
        xml = xml.replace("{VIDEO_NAME_PATTERN}", name_pattern)
        xml = xml.replace("{PUBLISH_LINKED}", str(publish_linked))
        
        return xml
        
        
    def get_ffmpeg_quicktime_encode_parameters(self):
        """
        Control how quicktimes are generated before being uploaded to Shotgun.
        These quicktimes are generated inside flame using ffmpeg version SVN-r17733.
        Note that the syntax has changed somewhat in more recent version of ffmpeg
        and be careful to test that all parameters and traits you wish to customize
        are included and supported in this particular build of ffmpeg.
        
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
        params += "-crf 20 " 
        
        return params
            
    def get_local_quicktime_preferred_height(self, width, height):
        """
        Control the preferred height of the local quicktime movie that is generated.
        The quicktime generation will try to match this as closely as possible, but may
        change it depending on technical constraints (for example, the aspect ratio needs to
        be preserved exactly and width and height both need to be factors of 2.)
        
        :param width: The width in pixels of the input images 
        :param height: The height in pixels of the input images
        :returns: The desired height.
        """
        return 1080

    def get_local_quicktime_ffmpeg_encode_parameters(self):
        """
        Control how quicktimes are generated for local playback in tools such as RV.
        
        These quicktimes are generated inside flame using ffmpeg version SVN-r17733.
        Note that the syntax has changed somewhat in more recent version of ffmpeg
        and be careful to test that all parameters and traits you wish to customize
        are included and supported in this particular build of ffmpeg.
        
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
