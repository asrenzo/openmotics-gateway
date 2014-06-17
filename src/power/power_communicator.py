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
Module to communicate with the power modules.

Created on Dec 29, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import traceback

import time
from threading import Thread, Lock

from serial_utils import printable, CommunicationTimedOutException

import power.power_api as power_api
from power.power_command import crc7
from power.time_keeper import TimeKeeper

class PowerCommunicator(object):
    """ Uses a serial port to communicate with the power modules. """

    def __init__(self, serial, power_controller, verbose=False, time_keeper_period=60,
                 address_mode_timeout=300):
        """ Default constructor.

        :param serial: Serial port to communicate with
        :type serial: Instance of :class`RS485`
        :param verbose: Print all serial communication to stdout.
        :type verbose: boolean.
        """
        self.__serial = serial
        self.__serial_lock = Lock()
        self.__serial_bytes_written = 0
        self.__serial_bytes_read = 0
        self.__cid = 1

        self.__address_mode = False
        self.__address_mode_stop = False
        self.__address_thread = None
        self.__address_mode_timeout = address_mode_timeout
        self.__power_controller = power_controller

        self.__last_success = 0

        if time_keeper_period != 0:
            self.__time_keeper = TimeKeeper(self, power_controller, time_keeper_period)
        else:
            self.__time_keeper = None

        self.__verbose = verbose

    def start(self):
        """ Start the power communicator. """
        if self.__time_keeper != None:
            self.__time_keeper.start()

    def get_bytes_written(self):
        """ Get the number of bytes written to the power modules. """
        return self.__serial_bytes_written

    def get_bytes_read(self):
        """ Get the number of bytes read from the power modules. """
        return self.__serial_bytes_read

    def get_seconds_since_last_success(self):
        """ Get the number of seconds since the last successful communication. """
        if self.__last_success == 0:
            return 0 ## No communication - return 0 sec since last success
        else:
            return time.time() - self.__last_success

    def __get_cid(self):
        """ Get a communication id """
        (ret, self.__cid) = (self.__cid, (self.__cid % 255) + 1)
        return ret

    def __write_to_serial(self, data):
        """ Write data to the serial port.

        :param data: the data to write
        :type data: string
        """
        if self.__verbose:
            print "%.3f writing to power: %s" % (time.time(), printable(data))
        self.__serial.write(data)
        self.__serial_bytes_written += len(data)

    def do_command(self, address, cmd, *data):
        """ Send a command over the serial port and block until an answer is received.
        If the power module does not respond within the timeout period, a
        CommunicationTimedOutException is raised.

        :param address: Address of the power module
        :type address: 2 bytes string
        :param cmd: the command to execute
        :type cmd: :class`PowerCommand`
        :param *data: data for the command
        :raises: :class`CommunicationTimedOutException` if power module did not respond in time
        :raises: :class`InAddressModeException` if communicator is in address mode
        :returns: dict containing the output fields of the command
        """
        if self.__address_mode:
            raise InAddressModeException()

        def do_once(address, cmd, *data):
            """ Send the command once. """
            cid = self.__get_cid()
            bytes = cmd.create_input(address, cid, *data)

            self.__write_to_serial(bytes)

            if address == power_api.BROADCAST_ADDRESS:
                return None # No reply on broadcast messages !
            else:
                (header, data) = self.__read_from_serial()

                if not cmd.check_header(header, address, cid):
                    raise Exception("Header did not match command")

                self.__last_success = time.time()
                return cmd.read_output(data)

        with self.__serial_lock:
            try:
                return do_once(address, cmd, *data)
            except:
                # Communication timed out, or header did not match, try again in 100 ms.
                print "First communication timed out !"
                time.sleep(0.1)
                return do_once(address, cmd, *data)

    def start_address_mode(self):
        """ Start address mode.

        :raises: :class`InAddressModeException` if communicator is in maintenance mode.
        """
        if self.__address_mode:
            raise InAddressModeException()

        self.__address_mode = True
        self.__address_mode_stop = False

        with self.__serial_lock:
            self.__address_thread = Thread(target=self.__do_address_mode,
                                           name="PowerCommunicator address mode thread")
            self.__address_thread.daemon = True
            self.__address_thread.start()

    def __do_address_mode(self):
        """ This code is running in a thread when in address mode. """
        expire = time.time() + self.__address_mode_timeout
        address_mode = power_api.set_addressmode()
        want_an_address = power_api.want_an_address()
        set_address = power_api.set_address()

        # AGT start
        bytes = address_mode.create_input(power_api.BROADCAST_ADDRESS, self.__get_cid(),
                                          power_api.ADDRESS_MODE)
        self.__write_to_serial(bytes)

        # Wait for WAA and answer.
        while not self.__address_mode_stop and time.time() < expire:
            try:
                (header, _) = self.__read_from_serial()

                if not want_an_address.check_header_partial(header):
                    LOGGER.warning("Received non WAA message in address mode")
                else:
                    (old_address, cid) = (ord(header[:2][1]), header[2:3])
                    # Ask power_controller for new address, and register it.
                    new_address = self.__power_controller.get_free_address()

                    if self.__power_controller.module_exists(old_address):
                        self.__power_controller.readdress_power_module(old_address, new_address)
                    else:
                        self.__power_controller.register_power_module(new_address)

                    # Send new address to power module
                    bytes = set_address.create_input(old_address, ord(cid), new_address)
                    self.__write_to_serial(bytes)

            except CommunicationTimedOutException:
                pass # Didn't receive a command, no problem.
            except Exception as exception:
                traceback.print_exc()
                LOGGER.warning("Got exception in address mode: %s", exception)

        # AGT stop
        bytes = address_mode.create_input(power_api.BROADCAST_ADDRESS, self.__get_cid(),
                                          power_api.NORMAL_MODE)
        self.__write_to_serial(bytes)

        self.__address_mode = False
        self.__address_thread = None

    def stop_address_mode(self):
        """ Stop address mode. """
        if not self.__address_mode:
            raise Exception("Not in address mode !")

        self.__address_mode_stop = True
        self.__address_thread.join()

    def in_address_mode(self):
        """ Returns whether the PowerCommunicator is in address mode. """
        return self.__address_mode

    def __read_from_serial(self):
        """ Read a PowerCommand from the serial port. """
        phase = 0
        index = 0

        header = ""
        length = 0
        data = ""
        crc = 0

        while phase < 8:
            bytes = self.__serial.read(1)

            if bytes == None or len(bytes) == 0:
                raise CommunicationTimedOutException()

            num_bytes = self.__serial.inWaiting()
            if num_bytes > 0:
                bytes += self.__serial.read(num_bytes)

            self.__serial_bytes_read += len(bytes)
            if self.__verbose:
                print "%.3f read from power: %s" % (time.time(), printable(bytes))

            for byte in bytes:
                if phase == 0:         ## Skip non 'R' bytes
                    if byte == 'R':
                        phase = 1
                    else:
                        phase = 0
                elif phase == 1:       ## Expect 'T'
                    if byte == 'T':
                        phase = 2
                    else:
                        raise Exception("Unexpected character")
                elif phase == 2:       ## Expect 'R'
                    if byte == 'R':
                        phase = 3
                        index = 0
                    else:
                        raise Exception("Unexpected character")
                elif phase == 3:        ## Read the header fields
                    header += byte
                    index += 1
                    if index == 8:
                        length = ord(byte)
                        if length > 0:
                            phase = 4
                            index = 0
                        else:
                            phase = 5
                elif phase == 4:        ## Read the data
                    data += byte
                    index += 1
                    if index == length:
                        phase = 5
                elif phase == 5:        ## Read the CRC code
                    crc = ord(byte)
                    phase = 6
                elif phase == 6:        ## Expect '\r'
                    if byte == '\r':
                        phase = 7
                    else:
                        raise Exception("Unexpected character")
                elif phase == 7:        ## Expect '\n'
                    if byte == '\n':
                        phase = 8
                    else:
                        raise Exception("Unexpected character")

        if crc7(header + data) != crc:
            raise Exception("CRC doesn't match")

        return (header, data)


class InAddressModeException(Exception):
    """ Raised when the power communication is in address mode. """
    def __init__(self):
        Exception.__init__(self)
