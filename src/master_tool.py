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

'''
Tool to control the master from the command line.

Created on Oct 4, 2012

@author: fryckbos
'''
import argparse
import sys
from ConfigParser import ConfigParser

from serial import Serial

import constants

import master.master_api as master_api
from master.master_communicator import MasterCommunicator

from serial_utils import CommunicationTimedOutException


def main():
    """ The main function. """
    parser = argparse.ArgumentParser(description='Tool to control the master.')
    parser.add_argument('--port', dest='port', action='store_true',
                        help='get the serial port device')
    parser.add_argument('--sync', dest='sync', action='store_true',
                        help='sync the serial port')
    parser.add_argument('--reset', dest='reset', action='store_true',
                        help='reset the master')
    parser.add_argument('--version', dest='version', action='store_true',
                        help='get the version of the master')

    args = parser.parse_args()

    config = ConfigParser()
    config.read(constants.get_config_file())

    port = config.get('OpenMotics', 'controller_serial')

    if args.port:
        print port
    elif args.sync or args.version or args.reset:
        master_serial = Serial(port, 115200)
        master_communicator = MasterCommunicator(master_serial)
        master_communicator.start()

        if args.sync:
            try:
                master_communicator.do_command(master_api.status())
            except CommunicationTimedOutException:
                print "Failed"
                sys.exit(1)
            else:
                print "Done"
                sys.exit(0)
        elif args.version:
            status = master_communicator.do_command(master_api.status())
            print "%d.%d.%d H%d" % (status['f1'], status['f2'], status['f3'], status['h'])
        elif args.reset:
            master_communicator.do_command(master_api.reset())
            print "Reset !"
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
