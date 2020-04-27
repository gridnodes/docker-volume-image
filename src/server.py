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
import flask
import json


class volumeDB():
    """
    Manage the volume data in a persistent storage.

    As the docker daemon does not send options of a specific volume for mounting
    it, these information needs to be stored persistent after creating the
    volume for later use. This context manager class provides a dictionary,
    which will automatically stored and restored from a JSON file to ensure this
    data is available not only for subsequent requests but also after a restart
    of the plugin.

    .. todo:: This context manager needs to be made thread safe.
    """

    def __init__(self, writable=False):
        """
        Initialize the context manager.


        :param writable: By default the data of this context manager can't be
            persistent. By changing this parameter to :py:class:`True`, modified
            contents will be dumped back to the JSON file on exit.
        """
        self._data = {}
        self._file = 'volumes.json'

        self._write = writable

    def __enter__(self) -> dict:
        """
        Enter the context.

        This method enteres the context and loads the contents of the volume
        database file. A reference to this database will be returned, so the
        application can use and alter this data.


        :returns: The volume database as dictionary.
        """
        with contextlib.suppress(FileNotFoundError):
            with open(self._file) as file:
                self._data = json.load(file)

        return self._data

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit the context.

        This method is called, when the context has been leaved. If no exception
        has been raised and the context was entered for write-access, the
        current database will be saved into the JSON file.
        """
        if self._write and not exc_type:
            with open(self._file, 'w') as file:
                json.dump(self._data, file, indent=4)


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
            'image': imageName(req['Opts']['image'])
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
        # Check, if the volume is already defined in the internal database to
        # avoid existing configurations being overwritten. The Docker daemon
        # has no check included to avoid this behavior.
        if data['name'] in volumes:
            return errorResponse('volume already exists')

        # Add the new volume configuration to the internal volume database, so
        # it is accessible for later use in other routes in subsequent requests.
        # An empty response will be returned to inform the Docker daemon about
        # successfully creating the volume.
        volumes[data['name']] = {
            'image': data['image']
        }
        return response()


# If this script is executed as application or loaded as main python script, run
# a simple web server to run the flask app.
if __name__ == "__main__":
    app.run()
