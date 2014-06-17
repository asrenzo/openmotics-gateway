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
Tests for MasterCommunicator module.

Created on Sep 10, 2012

@author: fryckbos
'''
import unittest
import threading
import time

from master.master_communicator import MasterCommunicator, InMaintenanceModeException, \
                                       BackgroundConsumer, CrcCheckFailedException
import master.master_api as master_api

from serial_tests import SerialMock, sin, sout
from serial_utils import CommunicationTimedOutException

class MasterCommunicatorTest(unittest.TestCase):
    """ Tests for MasterCommunicator class """

    def test_do_command(self):
        """ Test for standard behavior MasterCommunicator.do_command. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        serial_mock = SerialMock(
                        [sin(action.create_input(1, in_fields)),
                         sout(action.create_output(1, out_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        output = comm.do_command(action, in_fields)
        self.assertEquals("OK", output["resp"])

    def test_do_command_timeout(self):
        """ Test for timeout in MasterCommunicator.do_command. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}

        serial_mock = SerialMock([sin(action.create_input(1, in_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        try:
            comm.do_command(action, in_fields)
            self.assertTrue(False)
        except CommunicationTimedOutException:
            pass

    def test_do_command_timeout_test_ongoing(self):
        """ Test if communication resumes after timeout. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        serial_mock = SerialMock([sin(action.create_input(1, in_fields)),
                                  sin(action.create_input(2, in_fields)),
                                  sout(action.create_output(2, out_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        try:
            comm.do_command(action, in_fields)
            self.assertTrue(False)
        except CommunicationTimedOutException:
            pass

        output = comm.do_command(action, in_fields)
        self.assertEquals("OK", output["resp"])

    def test_do_command_passthrough(self):
        """ Test for the do_command with passthrough data. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        serial_mock = SerialMock(
                        [sin(action.create_input(1, in_fields)),
                         sout("hello" + action.create_output(1, out_fields)),
                         sin(action.create_input(2, in_fields)),
                         sout(action.create_output(2, out_fields) + "world"),
                         sin(action.create_input(3, in_fields)),
                         sout("hello" + action.create_output(3, out_fields) + " world"),
                         sin(action.create_input(4, in_fields)),
                         sout("hello"), sout(action.create_output(4, out_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("world", comm.get_passthrough_data())

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello world", comm.get_passthrough_data())

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())

    def test_do_command_split_data(self):
        """ Test MasterCommunicator.do_command when the data is split over multiple reads. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        sequence = []
        for i in range(1, 18):
            sequence.append(sin(action.create_input(i, in_fields)))
            output_bytes = action.create_output(i, out_fields)
            sequence.append(sout(output_bytes[:i]))
            sequence.append(sout(output_bytes[i:]))

        serial_mock = SerialMock(sequence)

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        for i in range(1, 18):
            self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])

    def test_send_passthrough_data(self):
        """ Test the passthrough if no other communications are going on. """
        pt_input = "data from passthrough"
        pt_output = "got it !"
        serial_mock = SerialMock([sin(pt_input), sout(pt_output)])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        comm.send_passthrough_data(pt_input)
        self.assertEquals(pt_output, comm.get_passthrough_data())

    def test_passthrough_output(self):
        """ Test the passthrough output if no other communications are going on. """
        serial_mock = SerialMock([sout("passthrough"), sout(" my "), sout("data")])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        self.assertEquals("passthrough", comm.get_passthrough_data())
        self.assertEquals(" my ", comm.get_passthrough_data())
        self.assertEquals("data", comm.get_passthrough_data())

    def test_maintenance_mode(self):
        """ Test the maintenance mode. """
        serial_mock = SerialMock([sin(master_api.to_cli_mode().create_input(0)),
                                  sout("OK"), sin("error list\r\n"), sout("the list\n"),
                                  sin("exit\r\n")])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        comm.start_maintenance_mode()

        try:
            comm.send_passthrough_data("test")
            self.assertTrue(False)
        except InMaintenanceModeException:
            pass

        try:
            comm.do_command(None, None)
            self.assertTrue(False)
        except InMaintenanceModeException:
            pass

        self.assertEquals("OK", comm.get_maintenance_data())
        comm.send_maintenance_data("error list\r\n")
        self.assertEquals("the list\n", comm.get_maintenance_data())
        comm.stop_maintenance_mode()

    def test_maintenance_passthrough(self):
        """ Test the behavior of passthrough in maintenance mode. """
        serial_mock = SerialMock([
                        sout("For passthrough"), sin(master_api.to_cli_mode().create_input(0)),
                        sout("OK"), sin("error list\r\n"), sout("the list\n"),
                        sin("exit\r\n"), sout("Passthrough again")])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        def passthrough_thread():
            """ Background thread that reads the passthrough data. """
            self.assertEquals("For passthrough", comm.get_passthrough_data())
            self.assertEquals("Passthrough again", comm.get_passthrough_data())

        thread = threading.Thread(target=passthrough_thread)
        thread.start()

        comm.start_maintenance_mode()
        self.assertEquals("OK", comm.get_maintenance_data())
        comm.send_maintenance_data("error list\r\n")
        self.assertEquals("the list\n", comm.get_maintenance_data())
        comm.stop_maintenance_mode()

        thread.join()

    def test_background_consumer(self):
        """ Test the background consumer mechanism. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        serial_mock = SerialMock([
                        sout("OL\x00\x01\x03\x0c\r\n"), sin(action.create_input(1, in_fields)),
                        sout("junkOL\x00\x02\x03\x0c\x05\x06\r\n here"),
                        sout(action.create_output(1, out_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)

        got_output = {"phase" : 1}

        def callback(output):
            """ Callback that check if the correct result was returned for OL. """
            if got_output["phase"] == 1:
                self.assertEquals([(3, int(12 * 10.0 / 6.0))], output["outputs"])
                got_output["phase"] = 2
            elif got_output["phase"] == 2:
                self.assertEquals([(3, int(12 * 10.0 / 6.0)), (5, int(6 * 10.0 / 6.0))],
                                  output["outputs"])
                got_output["phase"] = 3

        comm.register_consumer(BackgroundConsumer(master_api.output_list(), 0, callback))
        comm.start()

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals(3, got_output["phase"])
        self.assertEquals("junk here", comm.get_passthrough_data())

    def test_bytes_counter(self):
        """ Test the number of bytes written and read from the serial port. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}
        out_fields = {"resp": "OK"}

        serial_mock = SerialMock(
                        [sin(action.create_input(1, in_fields)),
                         sout("hello"),
                         sout(action.create_output(1, out_fields))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        self.assertEquals("OK", comm.do_command(action, in_fields)["resp"])
        self.assertEquals("hello", comm.get_passthrough_data())

        self.assertEquals(21, comm.get_bytes_written())
        self.assertEquals(5 + 18, comm.get_bytes_read())

    def test_watchdog(self):
        """ Test the watchdog. """
        action = master_api.basic_action()
        in_fields = {"action_type": 1, "action_number": 2}

        serial_mock = SerialMock([sin(action.create_input(1, in_fields)),
                                  sin(action.create_input(2, in_fields)),
                                  sin(action.create_input(3, in_fields))])

        timeout = False
        watchdog = {}

        def callback():
            """ Callback for the watchdog """
            watchdog['done'] = True

        comm = MasterCommunicator(serial_mock, init_master=False,
                                  watchdog_period=4, watchdog_callback=callback)
        comm.start()

        try:
            comm.do_command(action, in_fields)
        except CommunicationTimedOutException:
            timeout = True

        time.sleep(6)

        self.assertTrue(timeout)
        self.assertFalse('done' in watchdog)

        try:
            comm.do_command(action, in_fields)
        except CommunicationTimedOutException:
            timeout = True

        self.assertTrue(timeout)

        try:
            comm.do_command(action, in_fields)
        except CommunicationTimedOutException:
            timeout = True

        time.sleep(6)

        self.assertTrue(timeout)
        self.assertTrue('done' in watchdog)

    def test_crc_checking(self):
        """ Test the crc checking in the MasterCommunciator. """
        action = master_api.sensor_humidity_list()

        out_fields = {}
        for i in range(0, 32):
            out_fields['hum%d' % i] = i
        out_fields['crc'] = [ord('C'), 3, 224]

        out_fields2 = {}
        for i in range(0, 32):
            out_fields2['hum%d' % i] = 2 * i
        out_fields2['crc'] = [ord('C'), 0, 0]

        serial_mock = SerialMock([sin(action.create_input(1)),
                                  sout(action.create_output(1, out_fields)),
                                  sin(action.create_input(2)),
                                  sout(action.create_output(2, out_fields2))])

        comm = MasterCommunicator(serial_mock, init_master=False)
        comm.start()

        output = comm.do_command(action)
        self.assertEquals(0, output['hum0'])
        self.assertEquals(1, output['hum1'])

        self.assertRaises(CrcCheckFailedException, lambda: comm.do_command(action))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
