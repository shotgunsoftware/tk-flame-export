# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .shot import Shot
from sgtk import TankError
import sgtk

class Sequence(object):
    """
    Class representing a sequence in Shotgun/Flame
    """

    def __init__(self, name):
        """
        Constructor

        :param name: Sequence name
        """
        self._name = name
        self._shotgun_id = None
        self._shots = {}

        self._app = sgtk.platform.current_bundle()

        # get some app settings configuring how shots are parented
        self._shot_parent_entity_type = self._app.get_setting("shot_parent_entity_type")
        self._shot_parent_link_field = self._app.get_setting("shot_parent_link_field")

    def __repr__(self):
        return "<Sequence %s %s>" % (self._shot_parent_entity_type, self._name)

    @property
    def name(self):
        """
        Returns the name of the sequence
        """
        return self._name

    @property
    def shotgun_id(self):
        """
        Returns shotgun id for this sequence
        """
        return self._shotgun_id

    @property
    def shots(self):
        """
        Shots associated with this sequence
        """
        return self._shots.values()




    def add_shot(self, shot_name):
        """
        Adds a shot to this sequence.

        :param shot_name: Shot name
        :returns: The constructed Shot object
        """
        self._shots[shot_name] = Shot(self, shot_name)
        return self._shots[shot_name]

    def get_shot(self, shot_name):
        """
        Returns a shot object given its name

        :param shot_name: name of shot to retrieve
        :returns: Shot object
        """
        if shot_name not in self._shots:
            raise ValueError("Cannot find shot % in %s" % (shot_name, self))

        return self._shots[shot_name]

    def process_shotgun_shot_structure(self):
        """
        Processes and populates Shotgun and filesystem data.

        - Ensures that the sequence exists in Shotgun
        - Ensures that the shots exist in Shotgun
        - Populates Shotgun data for Sequence and Shot objects
        - Creates folders on disk for any new objects
        - Computes the context for all shot objects
        """
        self._app.log_debug("Preparing export structure for %s %s and shots %s" % (
            self._shot_parent_entity_type,
            self._name,
            self._shots.keys())
        )

        self._app.engine.show_busy("Preparing Shotgun...", "Preparing Shots for export...")

        try:
            # find and create shots and sequence in Shotgun
            self._resolve_sg_shot_structure()

            # now get a list of all new shots
            new_shots = [shot for shot in self._shots.values() if shot.new_in_shotgun]

            # run folder creation for our newly created shots
            self._app.log_debug("Creating folders on for all new shots...")
            for (idx, shot) in enumerate(new_shots):
                # this is a new shot
                msg = "Step %s/%s: Creating folders for Shot %s..." % (idx+1, len(new_shots), shot.name)
                self._app.engine.show_busy("Preparing Shotgun...", msg)
                self._app.log_debug("Creating folders on disk for Shot id %s..." % shot)
                self._app.sgtk.create_filesystem_structure(
                    "Shot",
                    shot.shotgun_id,
                    engine="tk-flame"
                )
                self._app.log_debug("...folder creation complete")

            # establish a context for all objects
            self._app.engine.show_busy("Preparing Shotgun...", "Resolving Shot contexts...")
            self._app.log_debug("Caching contexts...")
            for shot in self._shots.values():
                shot.cache_context()

        finally:
            # kill progress indicator
            self._app.engine.clear_busy()

    def compute_shot_cut_changes(self):
        """
        Compute the difference between flame cut data
        and the registered shot data in Shotgun.

        :returns: A list of shotgun batch updates required
                  in order for Shotgun to be up to date with
                  Flame.
        """
        self._app.log_debug("Computing cut changes between Shotgun and Flame....")

        for seq in self._shots:
            # get a list of metadata objects for this sequence
            shot_metadata_list = self._shots[seq].values()
            # sort it by cut in
            shot_metadata_list.sort(key=lambda x: x.new_cut_in)
            # now loop over all items and set an incrementing cut order
            cut_index = 1
            for shot_metadata in shot_metadata_list:
                if shot_metadata.created_this_session:
                    num_created_shots += 1
                shot_metadata.new_cut_order = cut_index
                cut_index += 1

            # Now update frame ranges to make sure Shotgun matches Flame.
            #
            # ensure that we actually have frame ranges for this shot
            # it seems sometimes there are shots that don't actually contain any clips.
            # I think this is anomaly in Flame, but since we have spotted it in QA,
            # it's good to do this extra check in this code.
            if shot_metadata.new_cut_in is None or shot_metadata.new_cut_out is None:
                self.log_warning("No frame ranges calculated for Shot %s!" % shot_metadata.shotgun_id)

            # has the frame range changed?
            elif shot_metadata.shotgun_cut_in != shot_metadata.new_cut_in or \
                 shot_metadata.shotgun_cut_out != shot_metadata.new_cut_out or \
                 shot_metadata.shotgun_cut_order != shot_metadata.new_cut_order:

                duration = shot_metadata.new_cut_out - shot_metadata.new_cut_in + 1
                num_cut_changes += 1

                # note that at this point all shots are guaranteed to exist in Shotgun
                # since they were created in the initial export step.

                sg_cut_batch = {
                    "request_type": "update",
                    "entity_type": "Shot",
                    "entity_id": shot_metadata.shotgun_id,
                    "data": {
                        "sg_cut_in": shot_metadata.new_cut_in,
                        "sg_cut_out": shot_metadata.new_cut_out,
                        "sg_cut_duration": duration,
                        "sg_cut_order": shot_metadata.new_cut_order
                    }
                }

                self.log_debug("Registering cut change: %s" % pprint.pformat(sg_cut_batch))
                shotgun_batch_items.append(sg_cut_batch)

            else:
                self.log_debug("No frame changes detected. Shotgun and Flame are already in sync.")

    def create_cut(self):
        """
        Create cut in Shotgun
        """


    def _resolve_sg_structure(self):
        """
        Ensures that Shots and sequences exist in Shotgun.

        Will automatically create Shots and Sequences if necessary
        and assign task templates.

        Shotgun Shot and Sequence data for objects will be populated.
        """
        self._app.log_debug("Ensuring sequence and shots exists in Shotgun...")
        # get some configuration settings first
        shot_task_template = self._app.get_setting("task_template")
        if shot_task_template == "":
            shot_task_template = None

        parent_task_template = self._app.get_setting("shot_parent_task_template")
        if parent_task_template == "":
            parent_task_template = None

        # handy shorthand
        project = self._app.context.project

        # Ensure that a parent exists in Shotgun with the parent name
        self._app.engine.show_busy(
            "Preparing Shotgun...",
            "Locating %s %s..." % (self._shot_parent_entity_type, self.name)
        )

        self._app.log_debug("Locating Shot parent object in Shotgun...")
        sg_parent = self._app.shotgun.find_one(
            self._shot_parent_entity_type,
            [["code", "is", self.name], ["project", "is", project]]
        )

        if sg_parent:
            self._app.log_debug("Parent %s already exists in Shotgun." % sg_parent)
            self._shotgun_id = sg_parent["id"]

        else:
            # Create a new parent object in Shotgun

            # First see if we should assign a task template
            if parent_task_template:
                # resolve task template
                self._app.engine.show_busy("Preparing Shotgun...", "Loading task template...")
                sg_task_template = self._app.shotgun.find_one(
                    "TaskTemplate",
                    [["code", "is", parent_task_template]]
                )
                if not sg_task_template:
                    raise TankError(
                        "The task template '%s' does not exist in Shotgun!" % parent_task_template
                    )
            else:
                sg_task_template = None

            self._app.engine.show_busy(
                "Preparing Shotgun...",
                "Creating %s %s..." % (self._shot_parent_entity_type, self.name)
            )

            sg_parent = self._app.shotgun.create(
                self._shot_parent_entity_type,
                {"code": self.name,
                 "task_template": sg_task_template,
                 "description": "Created by the Shotgun Flame exporter.",
                 "project": project }
            )
            self._shotgun_id = sg_parent["id"]
            self._app.log_debug("Created parent %s" % sg_parent)


        # Locate a task template for shots
        if shot_task_template:
            # resolve task template
            self._app.engine.show_busy("Preparing Shotgun...", "Loading task template...")
            sg_task_template = self._app.shotgun.find_one(
                "TaskTemplate",
                [["code", "is", shot_task_template]]
            )
            if not sg_task_template:
                raise TankError(
                    "The task template '%s' does not exist in Shotgun!" % shot_task_template
                )
        else:
            sg_task_template = None

        # now attempt to retrieve metadata for all shots. Shots that are not found are created.
        self._app.engine.show_busy("Preparing Shotgun...", "Loading Shot data...")

        self._app.log_debug("Loading shots from Shotgun...")

        # get list of shots as strings
        shot_names = self._shots.keys()

        # find them in shotgun
        sg_shots = self._app.shotgun.find(
            "Shot",
            [["code", "in", shot_names],
             [self._shot_parent_link_field, "is", self._shotgun_id]],
            ["code", "sg_cut_in", "sg_cut_out", "sg_cut_order"]
        )
        self._app.log_debug("...got %s shots." % len(sg_shots))

        # add sg data to shot objects
        for sg_shot in sg_shots:
            shot_name = sg_shot["code"]
            self._shots[shot_name].set_sg_data(sg_shot, False)

        # create all shots that don't already exist
        sg_batch_data = []
        for shot in self._shots.values():
            if not shot.exists_in_shotgun:
                # this shot does not yet exist in Shotgun
                batch = {
                    "request_type": "create",
                    "entity_type": "Shot",
                    "data": {
                        "code": shot.name,
                        "description": "Created by the Shotgun Flame exporter.",
                        self._shot_parent_link_field: self._shotgun_id,
                        "task_template": sg_task_template,
                        "project": project
                    }
                }
                self._app.log_debug("Adding to Shotgun batch queue: %s" % batch)
                sg_batch_data.append(batch)

        if len(sg_batch_data) > 0:
            self._app.engine.show_busy("Preparing Shotgun...", "Creating new shots...")

            self._app.log_debug("Executing sg batch command....")
            sg_batch_response = self._app.shotgun.batch(sg_batch_data)
            self._app.log_debug("...done!")

            # register its data with Shot objects
            for sg_data in sg_batch_response:
                shot_name = sg_data["code"]
                self._shots[shot_name].set_sg_data(sg_data, True)


