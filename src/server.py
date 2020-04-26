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

import flask


def response(data: dict = None) -> flask.wrappers.Response:
    """
    Generate a JSON response.

    This method takes a given dictionary and converts it to a valid JSON
    response, which can be returned in any flask route to handle the request.


    :param data: The data to be converted into a JSON response. If this
        parameter is not set or :py:class:`None`, an empty response will be
        generated.

    :returns: A JSON response for `data`.
    """
    return flask.jsonify(data)


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


# If this script is executed as application or loaded as main python script, run
# a simple web server to run the flask app.
if __name__ == "__main__":
    app.run()
