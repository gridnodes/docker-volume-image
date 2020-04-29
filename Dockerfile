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

FROM python:3-alpine

# This image just contains the required python application and its dependencies.
#
# TODO: At the moment, there is no optimization for reducing the image size.
#       These should be added to provide a small docker plugin image.
RUN  pip install docker flask gunicorn
COPY src/ /plugin
