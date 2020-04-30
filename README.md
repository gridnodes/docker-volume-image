# Docker volume plugin for mounting Docker images

[![](https://img.shields.io/github/issues-raw/gridnodes/docker-volume-image.svg?style=flat-square)](https://github.com/gridnodes/docker-volume-image/issues)
[![](https://img.shields.io/badge/license-GPLv3+-blue.svg?style=flat-square)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/gridnodes/image.svg?style=flat-square)](https://hub.docker.com/r/gridnodes/image)


When deploying an application with Docker, it may require several containers
running from different images for different purposes. However, in some
situations it is required to share parts of an image in a second one.

For example, consider a simple web application provided with PHP and nginx:
Usually, the source code of the application needs to be mounted in both
containers or copied into a custom image for both PHP and nginx. While the PHP
image will be customized to the application, the default installation is often
sufficient for nginx. This volume plugin gives you the ability to share the
source code of your PHP application image with a default nginx container and
thus doesn't require a custom build nginx image anymore.


## Installation

For `x86_64` architecture this plugin is available on Docker Hub and can be
installed via Docker CLI:

```
docker plugin install gridnodes/image
```

#### Manual installation

For platforms other than `x86_64`, a manual build of this plugin needs to be
performed. The `make` utility will be used for convenience, but no additional
dependencies are required. To install this plugin, just download its latest
sources and use the following command in the downloaded folder:

```
cd docker-volume-image-master
make all enable PLUGIN_TAG=latest
```


## Usage

As this volume plugin simply mounts existing Docker images, no further
configuration is required. A new volume can easily be created via the Docker
CLI:

```
docker volume create -d gridnodes/image -o image=myapp appsources
```

The volume plugin takes the following options for creating a volume:

  * __image__ *(required)*: The image to be associated with this volume. It has
    the same format as for other Docker CLI commands (e.g. `org/myapp:latest`).
    It needs to be available when mounting the volume (at container start), as
    this plugin doesn't pull any images.
  * __path__: A subdirectory of the image to be mounted. If not defined, the
    entire image will be mounted.

After creating the volume, it can be mounted into the target container. Please
keep in mind to mount it as read-only to avoid accidentally altering its
contents *(see limitations for further details)*:

```
docker run -d -v appsources:/app:ro nginx
```

For updating the volume's image, its sufficient to pull the updated image from
the registry and restart the container. The plugin will mount the new image
automatically, as the associated image will be resolved during the volume mount
when starting the container using this volume.


## Limitations

* Volumes managed by this plugin should be mounted read-only always, as the
  image layer path will be passed through as it is. This plugin can't avoid
  mounting it read-write without adding additional overhead, so it's essential
  to add the read-only flag when mounting the volume into the container.

* This plugin doesn't use the overlay filesystem driver. Therefore, for images
  with multiple layers only the uppermost one is mounted as volume. As most
  images add the application source on top of an existing image, this should fit
  most needs without implementing the complex handling of mount points.

* This plugin can't block deleting the associated images while they're mounted
  in running containers, as the Docker daemon has no API for this operation
  implemented at the moment. Deleting a mounted image could result in
  inconsistency of your container.


## License

This project is licensed under the [GPLv3+](LICENSE).

&copy; 2020 mksec, Alexander Haase
