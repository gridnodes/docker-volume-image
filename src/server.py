#!/usr/bin/env python3

# This file is part of docker-volume-images.
#
# This program is free software: you can redistribute it and/or modify it under
# the  terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see
#
#  http://www.gnu.org/licenses/
#
#
# Copyright (C) 2020 mksec <support@mksec.de>

import contextlib
import docker
import flask
import json
import os
import portalocker


class VolumeNotFoundError(Exception):
    """
    Exception class for volumes not found.

    This exception is raised, if a volume is accessed, which is not known to the
    internal volume database.
    """
    pass


class volumeDB(portalocker.Lock):
    """
    Manage the volume data in a persistent storage.

    As the docker daemon does not send options of a specific volume for mounting
    it, these information needs to be stored persistent after creating the
    volume for later use. This context manager class provides a dictionary,
    which will automatically stored and restored from a JSON file to ensure this
    data is available not only for subsequent requests but also after a restart
    of the plugin.
    """

    def __init__(self, writable=False):
        """
        Initialize the context manager.


        :param writable: By default the data of this context manager can't be
            persistent. By changing this parameter to :py:class:`True`, modified
            contents will be dumped back to the JSON file on exit.
        """
        self._data = {}
        self._file = os.getenv('STATE_FILE', '/mnt/state/volume-image.json')
        self._write = writable

        # Initialize the file lock for the given state file. For write-access
        # the 'a+' mode will be used to dynamically create the file, if its not
        # existent yet.
        #
        # NOTE: For write-access 'w+' can't be used, as the file contents need
        #       to be loaded first before saving the altered state.
        super().__init__(self._file, mode=('a+' if self._write else 'r'))

    def __enter__(self) -> dict:
        """
        Enter the context.

        This method enters the context and loads the contents of the volume
        database file. A reference to this database will be returned, so the
        application can use and alter this data.


        :returns: The volume database as dictionary.
        """
        # If the persistent database file already exists, acquire the protective
        # lock and open the file. For write-access this is also required to
        # initially create the file and lock it.
        if os.path.exists(self._file) or self._write:
            self.acquire()

            # If the file is initially created, it's empty. However, the JSON
            # parser doesn't allow empty files to be loaded. Therefore the
            # following check will ensure to parse non-empty files only.
            if os.fstat(self.fh.fileno()).st_size > 0:
                self.fh.seek(0)
                self._data = json.load(self.fh)

        return self._data

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit the context.

        This method is called, when the context has been leaved. If no exception
        has been raised and the context was entered for write-access, the
        current database will be saved into the JSON file.
        """

        def cleanupDict(src):
            """
            Cleanup a dictionary.

            This function cleans up a dictionary by removing all keys having
            :py:class:`None` as value. Although this doesn't change the
            functionality of this application, it will be used for minifying the
            resulting JSON data to be dumped.

            .. warning:: This function alters the input dictionary. To keep the
                original state, the input dictionary should be copied first
                before passing the copied one to this function.


            :param src: The dictionary to be cleaned up.

            :returns: The cleaned up dictionary.
            """
            # The following code is based on a stackoverflow answer, licensed
            # under the terms of the MIT license.
            #
            #   https://stackoverflow.com/a/4256027
            for key, value in list(src.items()):
                if value is None:
                    del src[key]
                elif isinstance(value, dict):
                    cleanupDict(value)
            return src

        # If the volume database is opened in write-access mode and no exception
        # occurred, persist the current database to the state file as JSON.
        #
        # NOTE: As the file is opened in 'a+' mode for write-access to read its
        #       contents first, a manual seek and truncate needs to be performed
        #       before writing the data.
        if self._write and not exc_type:
            self.fh.seek(0)
            self.fh.truncate(0)
            json.dump(cleanupDict(self._data), self.fh, indent=4)

        # Release previously acquired locks and close opened file handles before
        # exiting the context.
        self.release()


def getVolume(name: str) -> dict:
    """
    Get the specification of for a volume.


    :param name: The volume to be looked up.

    :returns: The volume specification as dictionary.

    :raises VolumeNotFoundError: If the volume can't be found in the internal
        volume database, an exception will be raised.
    """
    try:
        with volumeDB() as volumes:
            return volumes[name]
    except KeyError as e:
        raise VolumeNotFoundError from e


def getVolumePath(name: str, supress: bool = False) -> str:
    """
    Get the path of a specific volume.

    This function gets the path of a specific image of the local docker daemon,
    so it can be mounted as volume.

    .. note:: This function returns just the uppermost layer of images, but not
        the paths of the underlaying layers. For most use cases this should be
        sufficient, as the application data shared between containers often is
        contained in the uppermost layer.


    :param name: The image to be mounted.
    :param suppress: If :py:class:`True`, no exception is raised, if the image
        is not available in the local Docker daemon.

    :returns: The path to be mounted as volume. If `suppress` is enabled and the
        image can't be found, :py:class:`None` will be returned.

    :raises docker.errors.ImageNotFound: The image `name` couldn't be found.
    """
    # A context manager will be used to conditionally suppress the exception
    # thrown, if the related Docker image can't be found by either suppressing
    # just the Docker exception or an empty tuple (no exceptions).
    with contextlib.suppress(docker.errors.ImageNotFound if supress else ()):
        vol = getVolume(name)
        img = docker.from_env().images.get(vol['image'])

        # Get the path of the linked docker image and the optional subdirectory
        # to be mounted. Both will be used to get the full mount path to be used
        # as volume and returned as string.
        imgPath = img.attrs['GraphDriver']['Data']['UpperDir']
        volPath = vol.get('path')
        return imgPath + (('/' + volPath) if volPath else '')


def request() -> dict:
    """
    Get the JSON request body.

    All plugin API requests of the Docker engine have a JSON request body. This
    function parses the passed data and returns it as dictionary.


    :returns: Dictionary of the parsed JSON request body.
    """
    return flask.request.get_json(force=True)


def response(data: dict = None) -> flask.wrappers.Response:
    """
    Generate a JSON response.

    This function takes a given dictionary and converts it to a valid JSON
    response, which can be returned in any flask route to handle the request.


    :param data: The data to be converted into a JSON response. If this
        parameter is not set or :py:class:`None`, an empty response will be
        generated.

    :returns: A JSON response for `data`.
    """
    return flask.jsonify(data)


def errorResponse(message: str, status: int = 400) -> flask.wrappers.Response:
    """
    Generate an error response.

    On errors, the Docker engine expects the error message to have a specific
    format. This function will generate an appropriate error response for a
    given `message`, which can be returned to the client.


    :param message: The error message.
    :param status: The status code for the generated HTTP response. By default
        this is an error 400 (Bad Request), but can be changed if necessary.

    :returns: An error response in JSON format.
    """
    return response({'Err': message}), status


########
# Routes
########

# Create a new flask app, which will be used to handle the routes defined below
# and provides additional methods and decorators.
app = flask.Flask(__name__)


@app.errorhandler(VolumeNotFoundError)
def handleVolumeNotFound(error: VolumeNotFoundError):
    """
    Exception handler for :py:class:`VolumeNotFoundError`.

    This exception handler generates an error response indicating that a given
    volume being accessed is not known to the internal volume database.


    :param error: The :py:class:`VolumeNotFoundError` exception to be handled.

    :returns: A HTTP not found error response.
    """
    return errorResponse(f'volume {error} not found', 404)


@app.errorhandler(docker.errors.APIError)
def handleVolumeNotFound(error: docker.errors.APIError):
    """
    Exception handler for :py:class:`docker.errors.APIError`.

    This exception handler generates an error response for all errors related to
    Docker. As these are server-side errors, these get a status 500 code, even
    if its a configuration related error (i.e. unknown image name).


    :param error: The exception to be handled.

    :returns: A HTTP server side error response.
    """
    return errorResponse(error.explanation, 500)


@app.route('/Plugin.Activate', methods=['POST'])
def pluginActivate():
    """
    Activate the plugin.

    This route will be called to activate the plugin and returns the APIs
    implemented by it. This plugin implements just the volume API.


    :returns: The APIs implemented in this plugin.
    """
    return response({
        'Implements': ['VolumeDriver']
    })


@app.route('/VolumeDriver.Capabilities', methods=['POST'])
def volumeCapabilities():
    """
    Get the volume plugin's capabilities.

    .. note:: Despite this route just returns the default values for all volume
        plugins, this route is defined to avoid an error 404 in the logs.


    :returns: The capabilities of this volume plugin.
    """
    return response({
        'Capabilities': {
            # The database of this volume plugin is standalone for each docker
            # node. Therefore the volumes are created local only and need to be
            # created on all nodes of a swarm.
            'Scope': 'local'
        }
    })


@app.route('/VolumeDriver.Create', methods=['POST'])
def volumeCreate():
    """
    Create a new volume.

    This route creates a new volume according to the Docker volume plugin API
    specification from the given volume name and additional options passed by
    the client.

    .. note:: As the plugin doesn't manage actual volume data, but just mounts
        existing Docker images, a volume create action will just register it in
        the internal volume database for later use.


    :returns: If the volume has been successfully created, an empty response
        will be returned. Otherwise an :py:func:`errorResponse` is generated.
    """

    def imageName(image: str) -> str:
        """
        Generate a valid image name with its tag set.

        The Python Docker API requires an image tag set to get and pull the
        specific image. If it's not set, the API will download all all tags of
        this image. Therefore, this helper function will append the `:latest`
        default tag to the image name, if no tag is given in the image name.


        :param image: The image name.

        :returns: The image name will with a tag, at least the default one.
        """
        return image + ['', ':latest'][':' not in image]

    # Process the request data passed by the Docker daemon to get the volume
    # name, the related Docker image to mount and additional options for
    # mounting the volume.
    try:
        req = request()
        data = {
            'name': req['Name'],
            'image': imageName(req['Opts']['image']),

            # optional parameters
            'path': req['Opts'].get('path')
        }
    except KeyError as e:
        # If a mandatory option for this volume plugin is not set, an error
        # response will be returned.
        #
        # NOTE: This error handler assumes, that the request sent by the Docker
        #       daemon is API specification compliant, as it can't differentiate
        #       between missing keys of the top level, or the options array.
        return errorResponse(f'missing option {e}')

    with volumeDB(True) as volumes:
        # Add the new volume configuration to the internal volume database, so
        # it is accessible for later use in other routes in subsequent requests.
        # An empty response will be returned to inform the Docker daemon about
        # successfully creating the volume.
        volumes[data['name']] = {
            'image': data['image'],
            'path':  data['path']
        }
        return response()


@app.route('/VolumeDriver.Remove', methods=['POST'])
def volumeRemove():
    """
    Remove a volume.

    This route removes a previously created volume from the internal volume
    database.


    :returns: If the volume has been successfully removed, an empty response
        will be returned.
    """
    volName = request()['Name']

    # Open the volume database with write access and remove the given volume. An
    # empty response will be returned to inform the Docker daemon about
    # successfully removing the volume.
    #
    # NOTE: If the volume is not existent, no error will be thrown, as it seems
    #       to be removed already - which is what this route should do.
    with volumeDB(True) as volumes:
        with contextlib.suppress(KeyError):
            volumes.pop(volName, None)
            return response()


@app.route('/VolumeDriver.Get', methods=['POST'])
def volumeGet():
    """
    Get informations about a volume.

    This route get's informations about a specific volume of the internal volume
    database. This information is required in various steps of the volume
    workflow, most noticeable in the `volume inspect` command.


    :returns: Detailed information about the given volume.

    :raises VolumeNotFoundError: The given volume could not be found. See the
        :py:ref:`handleVolumeNotFound` exception handler for details.
    """
    # Get the passed volume name from the request body and look it up in the
    # internal volume database. There's no check, if the volume exists, as the
    # raised exception is handled automatically by an exception handler.
    #
    # NOTE: If the related docker image can't be found, no error is thrown, as
    #       there's no need to pull it before it needs to be mounted.
    volName = request()['Name']
    volPath = getVolumePath(volName, True)

    return response({
        'Volume': {
            'Name':       volName,
            'Mountpoint': volPath
        }
    })


@app.route('/VolumeDriver.List', methods=['POST'])
def volumeList():
    """
    Get a list of all volumes.

    This route generates a list of all volumes configured in this plugin and
    their mount paths, if available.


    :returns: A list of all volumes.
    """
    with volumeDB() as volumes:
        return response({
            'Volumes': list(map(
                lambda volName: {
                    'Name':       volName,
                    'Mountpoint': getVolumePath(volName, True)
                },
                volumes
            ))
        })


@app.route('/VolumeDriver.Mount', methods=['POST'])
@app.route('/VolumeDriver.Path',  methods=['POST'])
def volumeMount():
    """
    Mount the volume.

    This route gets the path of an image related to a specific volume to be
    mounted in the container to be started.

    .. note:: As this plugin provides existing paths of Docker images only, no
        actual mounting will be done by processing this route.


    :returns: The path to be mounted.
    """
    # Get the passed volume name from the request body and get the path to be
    # mounted from the related image.
    volName = request()['Name']
    volPath = getVolumePath(volName)

    # Get the filesystem root to get the prefix for Docker volume paths. This is
    # required, as the v2 volume plugin API requires plugins to mount the volume
    # in a dedicated folder instead of granting full filesystem access. By
    # prefixing the path with '/..', the PropagatedMount path will be bypassed
    # and the real filesystem root accessed.
    rootDir = docker.from_env().info()['DockerRootDir']
    volRoot = '/'.join(map(
        lambda x: '..' if x else '',
        (rootDir + '/plugins/pluginID/rootfs').split('/')
    ))

    return response({
        'Mountpoint': volRoot + volPath
    })


@app.route('/VolumeDriver.Unmount', methods=['POST'])
def volumeUnmount():
    """
    Unmount the volume.

    This route is called on volume unmount. However, as this plugin provides
    existing paths of the Docker images only, no additional steps need to be
    performed and an empty response can be returned always.


    :returns: An empty response.
    """
    return response()


# If this script is executed as application or loaded as main python script, run
# a simple web server to run the flask app.
if __name__ == "__main__":
    app.run()
