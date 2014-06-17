'''
OpenMotics - Gateway
Copyright (C) 2014 - OpenMotics <info@openmotics.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
'''

""" The update modules provides the update functionality. """

import sys
import hashlib
import traceback
import subprocess

from ConfigParser import ConfigParser

from constants import get_config_file, get_update_script, get_update_output_file, get_update_file

def md5(filename):
    """ Generate the md5 sum of a file.

    :param filename: the name of the file to hash.
    :returns: md5sum
    """
    md5_hash = hashlib.md5()
    with open(filename, 'rb') as file_to_hash:
        for chunk in iter(lambda: file_to_hash.read(128 * md5_hash.block_size), ''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def update(version, md5_server):
    """ Execute the actual update: extract the archive and execute the bash update script.

    :param version: the new version (after the update).
    :param md5_sum: the md5 sum provided by the server.
    """
    update_file = get_update_file()

    md5_client = md5(update_file)
    if md5_server != md5_client:
        raise Exception("MD5 of client (" + str(md5_client) + ") and server (" + str(md5_server) +
                        ") don't match")

    extract = subprocess.Popen("cd `dirname " + update_file + "`; tar xzf " + update_file,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    ret = extract.wait()
    extract_output = extract.stdout.read()

    if ret != 0:
        raise Exception("Extraction failed: " + extract_output)

    update_script = subprocess.Popen(get_update_script() + " `dirname " + update_file + "`",
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    ret = update_script.wait()
    update_output = update_script.stdout.read()

    cleanup = subprocess.Popen("rm -Rf `dirname " + update_file + "`/*",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    cleanup.wait()
    cleanup_output = update_script.stdout.read()

    if ret != 0:
        raise Exception("Error during update (ret=" + str(ret) + ") : " + update_output)
    else:
        config = ConfigParser()
        config.read(get_config_file())
        config.set('OpenMotics', 'version', version)
        with open(get_config_file(), 'wb') as configfile:
            config.write(configfile)

        return extract_output + "\n" + update_output + "\n" + cleanup_output


def main():
    """ The main function. """
    if len(sys.argv) != 3:
        print "Usage: python " + __file__ + " version md5sum"
        sys.exit(1)
    else:
        (version, md5_sum) = (sys.argv[1], sys.argv[2])
        error = None
        output = None

        try:
            output = update(version, md5_sum)
        except:
            error = traceback.format_exc()
        finally:
            update_output_file = open(get_update_output_file(), "w")
            update_output_file.write(version + "\n")
            if error != None:
                update_output_file.write("Update failed " + traceback.format_exc())
            else:
                update_output_file.write(output)
            update_output_file.close()


if __name__ == "__main__":
    main()
