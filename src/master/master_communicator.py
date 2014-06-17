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
Module to communicate with the master.

Created on Sep 10, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import os
import sys
import time
from threading import Thread, Lock, Event
from Queue import Queue, Empty

import master_api
from master_command import Field, printable
from serial_utils import CommunicationTimedOutException

class MasterCommunicator(object):
    """ Uses a serial port to communicate with the master and updates the output state.
    Provides methods to send MasterCommands, Passthrough and Maintenance. A watchdog checks the
    state of the communication: if more than 1 timeout between 2 watchdog checks is received, the
    communication is not working properly and watchdog callback is called.
    """

    def __init__(self, serial, init_master=True, verbose=False,
                 watchdog_period=150, watchdog_callback=lambda: os._exit(1),
                 passthrough_timeout=0.2):
        """ Default constructor.

        :param serial: Serial port to communicate with
        :type serial: Instance of :class`serial.Serial`
        :param init_master: Send an initialization sequence to the master to make sure we are in \
        CLI mode. This can be turned of for testing.
        :type init_master: boolean.
        :param verbose: Print all serial communication to stdout.
        :type verbose: boolean.
        :param watchdog_period: The number of seconds between two watchdog checks.
        :type watchdog_perdiod: integer.
        :param watchdog_callback: The action to call if the watchdog detects a communication \
        problem.
        :type watchdog_callback: function without arguments.
        :param passthrough_timeout: The time to wait for an answer on a passthrough message \
        (in sec)
        :type passthrough_timeout: float.
        """
        self.__init_master = init_master
        self.__verbose = verbose

        self.__serial = serial
        self.__serial_write_lock = Lock()
        self.__command_lock = Lock()
        self.__serial_bytes_written = 0
        self.__serial_bytes_read = 0
        self.__timeouts = 0

        self.__cid = 1

        self.__maintenance_mode = False
        self.__maintenance_queue = Queue()

        self.__consumers = []

        self.__passthrough_mode = False
        self.__passthrough_timeout = passthrough_timeout
        self.__passthrough_queue = Queue()
        self.__passthrough_done = Event()

        self.__last_success = 0

        self.__stop = False

        self.__read_thread = Thread(target=self.__read, name="MasterCommunicator read thread")
        self.__read_thread.daemon = True

        self.__watchdog_period = watchdog_period
        self.__watchdog_callback = watchdog_callback
        self.__watchdog_thread = Thread(target=self.__watchdog,
                                        name="MasterCommunicator watchdog thread")
        self.__watchdog_thread.daemon = True

    def start(self):
        """ Start the MasterComunicator, this starts the background read thread. """
        if self.__init_master:

            def flush_serial_input():
                """ Try to read from the serial input and discard the bytes read. """
                data = self.__serial.read(1)
                while len(data) > 0:
                    data = self.__serial.read(1)

            self.__serial.timeout = 1
            self.__serial.write(" "*18 + "\r\n")
            flush_serial_input()
            self.__serial.write("exit\r\n")
            flush_serial_input()
            self.__serial.write(" "*10)
            flush_serial_input()
            self.__serial.timeout = None

        self.__stop = False
        self.__read_thread.start()
        self.__watchdog_thread.start()

    def get_bytes_written(self):
        """ Get the number of bytes written to the Master. """
        return self.__serial_bytes_written

    def get_bytes_read(self):
        """ Get the number of bytes read from the Master. """
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
        with self.__serial_write_lock:
            if self.__verbose:
                print "%.3f writing to serial: %s" % (time.time(), printable(data))
            self.__serial.write(data)
            self.__serial_bytes_written += len(data)

    def register_consumer(self, consumer):
        """ Register a customer consumer with the communicator. An instance of :class`Consumer`
        will be removed when consumption is done. An instance of :class`BackgroundConsumer` stays
        active and is thus able to consume multiple messages.

        :param consumer: The consumer to register.
        :type consumer: Consumer or BackgroundConsumer.
        """
        self.__consumers.append(consumer)

    def do_command(self, cmd, fields=None, timeout=1):
        """ Send a command over the serial port and block until an answer is received.
        If the master does not respond within the timeout period, a CommunicationTimedOutException
        is raised

        :param cmd: specification of the command to execute
        :type cmd: :class`MasterCommand.MasterCommandSpec`
        :raises: :class`CommunicationTimedOutException` if master did not respond in time
        :raises: :class`InMaintenanceModeException` if master is in maintenance mode
        :returns: dict containing the output fields of the command
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()

        if fields is None:
            fields = dict()

        cid = self.__get_cid()
        consumer = Consumer(cmd, cid)
        inp = cmd.create_input(cid, fields)

        with self.__command_lock:
            self.__consumers.append(consumer)
            self.__write_to_serial(inp)
            try:
                result = consumer.get(timeout).fields
                if cmd.output_has_crc() and not self.__check_crc(cmd, result):
                    raise CrcCheckFailedException()
                else:
                    self.__last_success = time.time()
                    return result
            except CommunicationTimedOutException:
                self.__timeouts += 1
                raise

    def __check_crc(self, cmd, result):
        """ Calculate the CRC of the data for a certain master command.

        :param cmd: instance of MasterCommandSpec.
        :param result: A dict containing the result of the master command.
        :returns: boolean
        """
        crc = 0
        for field in cmd.output_fields:
            if Field.is_crc(field):
                break
            else:
                for byte in field.encode(result[field.name]):
                    crc += ord(byte)

        return result['crc'] == [67, (crc / 256), (crc % 256)]

    def __passthrough_wait(self):
        """ Waits until the passthrough is done or a timeout is reached. """
        if self.__passthrough_done.wait(self.__passthrough_timeout) != True:
            LOGGER.info("Timed out on passthrough message")

        self.__passthrough_mode = False
        self.__command_lock.release()

    def send_passthrough_data(self, data):
        """ Send raw data on the serial port.

        :param data: string of bytes with raw command for the master.
        :raises: :class`InMaintenanceModeException` if master is in maintenance mode.
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()

        if not self.__passthrough_mode:
            self.__command_lock.acquire()
            self.__passthrough_done.clear()
            self.__passthrough_mode = True
            passthrough_thread = Thread(target=self.__passthrough_wait)
            passthrough_thread.daemon = True
            passthrough_thread.start()

        self.__write_to_serial(data)

    def get_passthrough_data(self):
        """ Get data that wasn't consumed by do_command.
        Blocks if no data available or in maintenance mode.

        :returns: string containing unprocessed output
        """
        data = self.__passthrough_queue.get()
        if data[-4:] == '\r\n\r\n':
            self.__passthrough_done.set()
        return data

    def start_maintenance_mode(self):
        """ Start maintenance mode.

        :raises: :class`InMaintenanceModeException` if master is in maintenance mode.
        """
        if self.__maintenance_mode:
            raise InMaintenanceModeException()

        self.__maintenance_mode = True

        self.send_maintenance_data(master_api.to_cli_mode().create_input(0))

    def send_maintenance_data(self, data):
        """ Send data to the master in maintenance mode.

        :param data: data to send to the master
        :type data: string
         """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")

        self.__write_to_serial(data)

    def get_maintenance_data(self):
        """ Get data from the master in maintenance mode.

        :returns: string containing unprocessed output
        """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")

        try:
            return self.__maintenance_queue.get(timeout=1)
        except Empty:
            return None

    def stop_maintenance_mode(self):
        """ Stop maintenance mode. """
        if not self.__maintenance_mode:
            raise Exception("Not in maintenance mode !")

        self.send_maintenance_data("exit\r\n")

        self.__maintenance_mode = False

    def in_maintenance_mode(self):
        """ Returns whether the MasterCommunicator is in maintenance mode. """
        return self.__maintenance_mode

    def __get_start_bytes(self):
        """ Create a dict that maps the start byte to a list of consumers. """
        start_bytes = {}
        for consumer in self.__consumers:
            start_byte = consumer.get_prefix()[0]
            if start_byte in start_bytes:
                start_bytes[start_byte].append(consumer)
            else:
                start_bytes[start_byte] = [consumer]
        return start_bytes

    def __watchdog(self):
        """ Run in the background watchdog thread: checks the number of timeouts per minute. If the
        number of timeouts is larger than 1, the watchdog callback is called. """
        while not self.__stop:
            (timeouts, self.__timeouts) = (self.__timeouts, 0)
            if timeouts > 1:
                sys.stderr.write("Watchdog detected problems in communication !\n")
                self.__watchdog_callback()
            time.sleep(self.__watchdog_period)

    def __read(self):
        """ Code for the background read thread: reads from the serial port, checks if
        consumers for incoming bytes, if not: put in pass through buffer.
        """
        def consumer_done(consumer):
            """ Callback for when consumer is done. ReadState does not access parent directly. """
            if isinstance(consumer, Consumer):
                self.__consumers.remove(consumer)

        class ReadState(object):
            """" The read state keeps track of the current consumer and the partial result
            for that consumer. """
            def __init__(self):
                self.current_consumer = None
                self.partial_result = None

            def should_resume(self):
                """ Checks whether we should resume consuming data with the current_consumer. """
                return self.current_consumer != None

            def should_find_consumer(self):
                """ Checks whether we should find a new consumer. """
                return self.current_consumer == None

            def set_consumer(self, consumer):
                """ Set a new consumer. """
                self.current_consumer = consumer
                self.partial_result = None

            def consume(self, data):
                """ Consume the bytes in data using the current_consumer, and return the bytes
                that were not used. """
                try:
                    (bytes_consumed, result, done) = \
                        read_state.current_consumer.consume(data, read_state.partial_result)
                except ValueError, value_error:
                    sys.stderr.write("Got ValueError: " + str(value_error))
                    return ""
                else:
                    if done:
                        consumer_done(self.current_consumer)
                        self.current_consumer.deliver(result)

                        self.current_consumer = None
                        self.partial_result = None

                        return data[bytes_consumed:]
                    else:
                        self.partial_result = result
                        return ""

        read_state = ReadState()
        data = ""

        while not self.__stop:
            data += self.__serial.read(1)
            num_bytes = self.__serial.inWaiting()
            if num_bytes > 0:
                data += self.__serial.read(num_bytes)
            if data != None and len(data) > 0:
                self.__serial_bytes_read += (1 + num_bytes)

                if self.__verbose:
                    print "%.3f read from serial: %s" % (time.time(), printable(data))

                if read_state.should_resume():
                    data = read_state.consume(data)

                # No else here: data might not be empty when current_consumer is done
                if read_state.should_find_consumer():
                    start_bytes = self.__get_start_bytes()
                    leftovers = "" # for unconsumed bytes; these will go to the passthrough.

                    while len(data) > 0:
                        if data[0] in start_bytes:
                            # Prefixes are 3 bytes, make sure we have enough data to match
                            if len(data) >= 3:
                                match = False
                                for consumer in start_bytes[data[0]]:
                                    if data[:3] == consumer.get_prefix():
                                        # Found matching consumer
                                        read_state.set_consumer(consumer)
                                        data = read_state.consume(data[3:]) # Strip off prefix
                                        # Consumers might have changed, update start_bytes
                                        start_bytes = self.__get_start_bytes()
                                        match = True
                                        break
                                if match:
                                    continue
                            else:
                                # All commands end with '\r\n', there are no prefixes that start
                                # with \r\n so the last bytes of a command will not get stuck
                                # waiting for the next serial.read()
                                break

                        leftovers += data[0]
                        data = data[1:]

                    if len(leftovers) > 0:
                        if not self.__maintenance_mode:
                            self.__passthrough_queue.put(leftovers)
                        else:
                            self.__maintenance_queue.put(leftovers)


class InMaintenanceModeException(Exception):
    """ An exception that is raised when the master is in maintenance mode. """
    def __init__(self):
        Exception.__init__(self)

class CrcCheckFailedException(Exception):
    """ This exception is raised if we receive a bad message. """
    def __init__(self):
        Exception.__init__(self)

class Consumer(object):
    """ A consumer is registered to the read thread before a command is issued.  If an output
    matches the consumer, the output will unblock the get() caller. """

    def __init__(self, cmd, cid):
        self.cmd = cmd
        self.cid = cid
        self.__queue = Queue()

    def get_prefix(self):
        """ Get the prefix of the answer from the master. """
        return self.cmd.action + str(chr(self.cid))

    def consume(self, data, partial_result):
        """ Consume data. """
        return self.cmd.consume_output(data, partial_result)

    def get(self, timeout):
        """ Wait until the master replies or the timeout expires.

        :param timeout: timeout in seconds
        :raises: :class`CommunicationTimedOutException` if master did not respond in time
        :returns: dict containing the output fields of the command
        """
        try:
            return self.__queue.get(timeout=timeout)
        except Empty:
            raise CommunicationTimedOutException()

    def deliver(self, output):
        """ Deliver output to the thread waiting on get(). """
        self.__queue.put(output)


class BackgroundConsumer(object):
    """ A consumer that runs in the background. The BackgroundConsumer does not provide get()
    but does a callback to a function whenever a message was consumed.
    """

    def __init__(self, cmd, cid, callback):
        """ Create a background consumer using a cmd, cid and callback.

        :param cmd: the MasterCommand to consume.
        :param cid: the communication id.
        :param callback: function to call when an instance was found.
        """
        self.cmd = cmd
        self.cid = cid
        self.callback = callback

    def get_prefix(self):
        """ Get the prefix of the answer from the master. """
        return self.cmd.action + str(chr(self.cid))

    def consume(self, data, partial_result):
        """ Consume data. """
        return self.cmd.consume_output(data, partial_result)

    def deliver(self, output):
        """ Deliver output to the thread waiting on get(). """
        self.callback(output)

