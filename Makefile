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

# This Makefile was inspired by the one provided with the Docker volume plugin
# for sshFS, which is licensed under the MIT license. Its source can be obtained
# from https://github.com/vieux/docker-volume-sshfs.

PLUGIN_NAME = gridnodes/image
PLUGIN_TAG ?= next


all: rootfs create

rootfs:
	docker build -t ${PLUGIN_NAME}:rootfs .
	mkdir -p ./build/rootfs
	docker create --name tmp ${PLUGIN_NAME}:rootfs >/dev/null
	docker export tmp | tar -x -C ./build/rootfs
	docker rm -vf tmp >/dev/null
	cp config.json ./build

create:
	docker plugin rm -f ${PLUGIN_NAME}:${PLUGIN_TAG} >/dev/null 2>&1 || true
	docker plugin create ${PLUGIN_NAME}:${PLUGIN_TAG} ./build

enable:
	docker plugin enable ${PLUGIN_NAME}:${PLUGIN_TAG}
