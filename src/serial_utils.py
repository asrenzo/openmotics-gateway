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

"""
Serial tools contains the RS485 wrapper, printable and CommunicationTimedOutException.

Created on Dec 29, 2012

@author: fryckbos
"""
import struct
import fcntl

class CommunicationTimedOutException(Exception):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self):
        Exception.__init__(self)

def printable(string):
    """ Converts non-printable characters into hex notation """

    hex_notation = " ".join(['%3d' % ord(c) for c in string])
    readable = "".join([c if ord(c) > 32 and ord(c) <= 126 else '.' for c in string])
    return hex_notation + "    " + readable

class RS485(object):
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        """ Initialize a rs485 connection using the serial port. """
        self.__serial = serial
        fileno = serial.fileno()
        serial_rs485 = struct.pack('hhhhhhhh', 3, 0, 0, 0, 0, 0, 0, 0)
        fcntl.ioctl(fileno, 0x542F, serial_rs485)
        serial.timeout = 1

    def write(self, data):
        """ Write data to serial port """
        self.__serial.write(data)

    def read(self, size):
        """ Read size bytes from serial port """
        return self.__serial.read(size)

    def inWaiting(self): #pylint: disable=C0103
        """ Get the number of bytes pending to be read """
        return self.__serial.inWaiting()
