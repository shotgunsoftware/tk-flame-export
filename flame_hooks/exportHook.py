# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

def preCustomExport(info, userData):
    """
    Hook called before a custom export begins. The export will be blocked
    until this function returns. This can be used to fill information that would
    have normally been extracted from the export window.
    
    :param info: Modifiable dictionary with info about the export. Contains the keys
                 - destinationHost: Host name where the exported files will be written to.
                 - destinationPath: Export path root.
                 - presetPath: Path to the preset used for the export.
    
    :param userData: Dictionary that could have been populated by previous export hooks and that
                     will be carried over into the subsequent export hooks.
                     This can be used by the hook to pass black box data around.
    """
    # first, get the toolkit app handle
    import sgtk
    e = sgtk.platform.current_engine()
    app = e.apps["tk-flame-export"]

    # get the preset that the user selected
    current_preset = userData["preset_title"]

    # create a session object in the app - this is how 
    # we keep track of what is going on
    session_id = app.create_export_session(current_preset)
    userData["session_id"] = session_id

    # --- at this point we could potentially pop up a UI
    # --- to gather additional parameters from the user

    # populate export settings
    info["destinationHost"] = app.get_destination_host(session_id)
    info["destinationPath"] = app.get_destination_path(session_id)
    info["presetPath"] = app.get_export_preset_path(session_id)
   
 
def preExportSequence(info, userData):
    """
    Hook called before a sequence export begins. The export will be blocked
    until this function returns.
    
    :param info: Information about the export. Contains the keys      
                 - destinationHost: Host name where the exported files will be written to.
                 - destinationPath: Export path root.
                 - sequenceName: Name of the exported sequence.
                 - shotNames: Tuple of all shot names in the exported sequence. 
                              Multiple segments could have the same shot name.
    
    :param userData: Dictionary that could have been populated by previous export hooks and that
                     will be carried over into the subsequent export hooks.
                     This can be used by the hook to pass black box data around.    
    """
    
    # Example of output coming from flame:
    # 
    # [PYTHON HOOK] Calling python hook function preExportSequence(
    # {'destinationHost': 'Mannes-MacBook-Pro-2.local', 
    #  'destinationPath': '/tmp', 
    #  'sequenceName': 'X-Ball Gladiator 3', 
    #  'shotNames': ('sh_0010', 'sh_0020', 'sh_0030', 'sh_10', 'sh_20', 'sh_30', 'sh_40')}, 
    # {'preset_name': 'sequence_export_2', 'session_id': '123'})
   
    # first, get the toolkit app handle
    import sgtk
    e = sgtk.platform.current_engine()
    app = e.apps["tk-flame-export"]

    # get the preset that the user selected
    # note that in the case of a non-tk export, there
    # may not be a session id.    
    session_id = userData.get("session_id")
    if session_id:
        # before the export happens call out to the 
        # toolkit export app to set up folder structure on disk
        app.prepare_export_structure(session_id, info["sequenceName"], info["shotNames"])


# def preExportAsset(info, userData):
#     print "preExportAsset!"
#     
#     info["namePattern"] = "<name>CUSTOM"

 
def postExportAsset(info, userData):
    """    
    Hook called after an asset export ends. The export will be blocked
    until this function returns.
    
    :param info: Dictionary with a number of parameters:
    
       destinationHost: Host name where the exported files will be written to.
       destinationPath: Export path root.
       namePattern:     List of optional naming tokens.
       resolvedPath:    Full file pattern that will be exported with all the tokens resolved.
       name:            Name of the exported asset.
       sequenceName:    Name of the sequence the asset is part of.
       shotName:        Name of the shot the asset is part of.
       assetType:       Type of exported asset. ( 'video', 'audio', 'batch', 'openClip', 'batchOpenClip' )
       isBackground:    True if the export of the asset happened in the background.
       backgroundJobId: Id of the background job given by the backburner manager upon submission. 
                        Empty if job is done in foreground.
       width:           Frame width of the exported asset.
       height:          Frame height of the exported asset.
       aspectRatio:     Frame aspect ratio of the exported asset.
       depth:           Frame depth of the exported asset. ( '8-bits', '10-bits', '12-bits', '16 fp' )
       scanFormat:      Scan format of the exported asset. ( 'FILED_1', 'FIELD_2', 'PROGRESSIVE' )
       fps:             Frame rate of exported asset.
       versionName:     Current version name of export (Empty if unversioned).
       versionNumber:   Current version number of export (0 if unversioned).
    
    :param userData: Dictionary that could have been populated by previous export hooks and that
                     will be carried over into the subsequent export hooks.
                     This can be used by the hook to pass black box data around.
    """
    
    # Examples of output: 
    #    
    # [PYTHON HOOK] Calling python hook function postExportAsset(
    # {'height': 1080L, 
    # 'destinationPath': '/Volumes/G-DRIVE mobile/tmp/', 
    # 'destinationHost': 'Mannes-MacBook-Pro-2.local', 
    # 'sourceOut': 432L, 
    # 'assetType': 'video', 
    # 'recordIn': 0L, 
    # 'sequenceFps': '23.976', 
    # 'width': 1920L, 
    # 'fps': '23.976', 
    # 'resolvedPath': 'X-Ball Gladiator 3/IMPORT/1920x1080/s0014.[00000430-00000431].dpx', 
    # 'sequenceName': 'X-Ball Gladiator 3', 
    # 'shotName': 'sh_0010',
    # 'assetName': '010_Jump_Sand', 
    # 'versionNumber': 0L, 
    # 'versionName': 'v<version>', 
    # 'recordOut': 2L, 
    # 'sourceIn': 430L, 
    # 'scanFormat': 'PROGRESSIVE', 
    # 'namePattern': '<name>/<tape>/<width>x<height>/s<segment>.<timecode><ext>', 
    # 'depth': '8-bit', 
    # 'isBackground': False, 
    # 'aspectRatio': 1.7777777910232544}, {})
    
    # first, get the toolkit app handle
    import sgtk
    e = sgtk.platform.current_engine()
    app = e.apps["tk-flame-export"]

    # get the preset that the user selected
    # note that in the case of a non-tk export, there
    # may not be a session id.    
    session_id = userData.get("session_id")
    if session_id:
        # tell the toolkit export app about this file
        app.register_publish(session_id, info)   
   

 
def postCustomExport(info, userData):
    """
    Hook called after a custom export ends. The export will be blocked
    until this function returns.
    
    :param info: Information about the export. Contains the keys      
                 - destinationHost: Host name where the exported files will be written to.
                 - destinationPath: Export path root.
                 - presetPath: Path to the preset used for the export.
    
    :param userData: Dictionary that could have been populated by previous export hooks and that
                     will be carried over into the subsequent export hooks.
                     This can be used by the hook to pass black box data around.
    """

    # Example input:
    #
    # [PYTHON HOOK] Calling python hook function postCustomExport(
    # {'destinationHost': 'localhost', 
    #  'destinationPath': '/tmp', 
    #  'presetPath': '/usr/discreet/flameassist_2015.2.pr99/export/presets/file_sequence/Jpeg (8-bit).xml'}, 
    # {'preset_name': 'sequence_export_2'})

    # first, get the toolkit app handle
    import sgtk
    e = sgtk.platform.current_engine()
    app = e.apps["tk-flame-export"]

    # get the preset that the user selected
    # note that in the case of a non-tk export, there
    # may not be a session id.
    session_id = userData.get("session_id")
    if session_id:
        app.post_process_export(session_id)

def getCustomExportProfiles(profiles):
    """
    Hook returning the custom export profiles to display to the user in the
    contextual menu.

    :param profiles: A dictionary of userData dictionaries where 
                     the keys are the name of the profiles to show in contextual menus.
    """
    import sgtk
    e = sgtk.platform.current_engine()
    app = e.apps["tk-flame-export"]
    
    for preset_title in app.get_export_presets(): 
        profiles[preset_title] = {"preset_title": preset_title}

