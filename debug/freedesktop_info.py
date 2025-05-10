#!/usr/bin/python3
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version("GnomeDesktop", "4.0")
from gi.repository import Gio, GnomeDesktop

MAX_WORKERS = os.cpu_count()

executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


def make_thumbnail(factory, filename):
    mtime = os.path.getmtime(filename)
    f = Gio.file_new_for_path(filename)
    uri = f.get_uri()
    print(f"URI: {uri}")  # Print URI to check its correctness
    info = f.query_info("standard::content-type", Gio.FileQueryInfoFlags.NONE, None)
    mime_type = info.get_content_type()

    try:
        # Check if a thumbnail already exists
        thumbnail_file = factory.lookup(uri, mtime)
        if thumbnail_file is not None:
            print("Path: %s", thumbnail_file)
            print("FRESH       %s" % uri)
            return True

        # Check if we can generate a thumbnail for the MIME type
        if not factory.can_thumbnail(uri, mime_type, mtime):
            print("UNSUPPORTED %s" % uri)
            return True

        # Attempt to generate the thumbnail
        # thumbnail = factory.generate_thumbnail(uri, mime_type)
        # if thumbnail is None:
        #     print("ERROR       %s" % uri)
        #     return False

        # Save the thumbnail
        print("OK          %s" % uri)
        # factory.save_thumbnail(thumbnail, uri, mtime)
    except gi.repository.GLib.GError as e:
        print(f"GError: {e.message}")  # Print the detailed error message
        print(f"Stack trace: {e}")
        print(f"ERROR {e}   {uri}")
        return False

    return True


def thumbnail_folder(factory, folder):
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            executor.submit(make_thumbnail(factory, os.path.join(dirpath, filename)))


def main(argv):
    factory = GnomeDesktop.DesktopThumbnailFactory()
    for filename in argv[1:]:
        if os.path.isdir(filename):
            thumbnail_folder(factory, filename)
        else:
            make_thumbnail(factory, filename)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
