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
Contains the SerialMock.

Created on Dec 29, 2012

@author: fryckbos
"""
import time
import threading
import unittest

from serial_utils import printable

def sin(data):
    """ Input for the SerialMock """
    return ('i', data)

def sout(data):
    """ Output from the SerialMock """
    return ('o', data)

class SerialMock(object):
    """ Mockup for :class`serial.Serial`.
    TODO Serial timeout is not implemented here
    TODO For sequence: [ sout(" "), sout("two") ]
         read() returns " "
         inWaiting() returns 3 instead of 0
    """

    def __init__(self, sequence, timeout=0):
        """ Takes a sequence of sin() and sout(). Check if we get the sin bytes on write(),
        gives the sout bytes to read(). """
        self.__sequence = sequence
        self.__timeout = timeout

        self.bytes_written = 0
        self.bytes_read = 0

    def write(self, data):
        """ Write data to serial port """
        while self.__sequence[0][0] == 'o':
            time.sleep(0.01)

        if data != self.__sequence[0][1]:
            raise Exception("Got wrong data in SerialMock: expected %s, got %s",
                            (printable(self.__sequence[0][1]), printable(data)))
        self.__sequence.pop(0)
        self.bytes_written += len(data)

    def read(self, size):
        """ Read size bytes from serial port """
        while len(self.__sequence) == 0 or self.__sequence[0][0] == 'i':
            time.sleep(0.01)

        if self.__timeout != 0 and self.__sequence[0][1] == '':
            time.sleep(self.__timeout)
            self.__sequence.pop(0)
            return ''
        else:
            ret = self.__sequence[0][1][:size]
            self.__sequence[0] = (self.__sequence[0][0], self.__sequence[0][1][size:])

            if len(self.__sequence[0][1]) == 0:
                self.__sequence.pop(0)

            self.bytes_read += len(ret)
            return ret

    def inWaiting(self): #pylint: disable=C0103
        """ Get the number of bytes pending to be read """
        if len(self.__sequence) == 0 or self.__sequence[0][0] == 'i':
            return 0
        else:
            return len(self.__sequence[0][1])

    def interrupt(self):
        """ Interrupt a read that is waiting until the end of time. """
        if len(self.__sequence) > 0:
            raise Exception("Can only interrupt read at end of stream")
        self.__sequence.append(sout("\x00"))

class SerialMockTest(unittest.TestCase):
    """ Tests for SerialMock class """

    def test_serial_mock(self):
        """ Tests for SerialMock. """
        serial_mock = SerialMock([sin("abc"), sout("def"), sin("g"), sout("h")])
        serial_mock.write("abc")
        self.assertEquals("d", serial_mock.read(1))
        self.assertEquals(2, serial_mock.inWaiting())
        self.assertEquals("ef", serial_mock.read(2))
        serial_mock.write("g")
        self.assertEquals("h", serial_mock.read(1))
        self.assertEquals(0, serial_mock.inWaiting())

    def test_threaded_serial_mock(self):
        """ Tests for SerialMock in thread, check if reads and writes are in sequence. """
        serial_mock = SerialMock([sin("abc"), sout("def"), sin("g"), sout("h")])
        phase = {'phase':0}

        def __reader(serial, phase):
            """ Code for reading from a differen thread, checks the output and phase. """
            self.assertEquals("d", serial.read(1))
            self.assertEquals(1, phase['phase'])
            phase['phase'] = 2
            self.assertEquals(2, serial.inWaiting())
            self.assertEquals("ef", serial.read(2))

            self.assertEquals("h", serial.read(1))
            self.assertEquals(3, phase['phase'])
            self.assertEquals(0, serial.inWaiting())

        threading.Thread(target=__reader, args=(serial_mock, phase)).start()

        serial_mock.write("abc")
        phase['phase'] = 1
        serial_mock.write("g")
        self.assertEquals(2, phase['phase'])
        phase['phase'] = 3

    def test_keep_read_waiting(self):
        """ Tests for serial mock, that checks if a read() stays waiting if there is
        no data available. """
        serial_mock = SerialMock([])
        phase = {'phase':0}

        def __timeout(serial, phase):
            """ Interrupts the read to make the test finish. """
            time.sleep(0.05)
            phase['phase'] = 1
            serial.interrupt()

        threading.Thread(target=__timeout, args=(serial_mock, phase)).start()

        serial_mock.read(1)
        self.assertEquals(1, phase['phase'])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
