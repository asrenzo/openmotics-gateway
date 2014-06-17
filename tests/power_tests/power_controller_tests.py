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
Tests for the power controller module.

Created on Dec 29, 2012

@author: fryckbos
'''
import unittest
import os

from power.power_controller import PowerController

class PowerControllerTest(unittest.TestCase):
    """ Tests for PowerController. """

    FILE = "test.db"

    def setUp(self): #pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(PowerControllerTest.FILE):
            os.remove(PowerControllerTest.FILE)

    def tearDown(self): #pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(PowerControllerTest.FILE):
            os.remove(PowerControllerTest.FILE)

    def __get_controller(self):
        """ Get a PowerController using FILE. """
        return PowerController(PowerControllerTest.FILE)

    def test_empty(self):
        """ Test an empty database. """
        power_controller = self.__get_controller()
        self.assertEquals({}, power_controller.get_power_modules())
        self.assertEquals(1, power_controller.get_free_address())

        power_controller.register_power_module(1)

        self.assertEquals({1: {'id': 1, 'address': 1, 'name': u'', 'input0': u'', 'input1': u'',
                               'input2': u'', 'input3': u'', 'input4': u'', 'input5': u'',
                               'input6': u'', 'input7': u'', 'sensor0': 0, 'sensor1': 0,
                               'sensor2': 0, 'sensor3': 0, 'sensor4': 0, 'sensor5': 0,
                               'sensor6': 0, 'sensor7': 0, 'times0': None, 'times1': None,
                               'times2': None, 'times3': None, 'times4': None, 'times5': None,
                               'times6': None, 'times7': None}},
                          power_controller.get_power_modules())

        self.assertEquals(2, power_controller.get_free_address())

        power_controller.register_power_module(5)
        self.assertEquals({1: {'id': 1, 'address': 1, 'name': u'', 'input0': u'', 'input1': u'',
                               'input2': u'', 'input3': u'', 'input4': u'', 'input5': u'',
                               'input6': u'', 'input7': u'', 'sensor0': 0, 'sensor1': 0,
                               'sensor2': 0, 'sensor3': 0, 'sensor4': 0, 'sensor5': 0,
                               'sensor6': 0, 'sensor7': 0, 'times0': None, 'times1': None,
                               'times2': None, 'times3': None, 'times4': None, 'times5': None,
                               'times6': None, 'times7': None},
                           2: {'id': 2, 'address': 5, 'name': u'', 'input0': u'', 'input1': u'',
                               'input2': u'', 'input3': u'', 'input4': u'', 'input5': u'',
                               'input6': u'', 'input7': u'', 'sensor0': 0, 'sensor1': 0,
                               'sensor2': 0, 'sensor3': 0, 'sensor4': 0, 'sensor5': 0,
                               'sensor6': 0, 'sensor7': 0, 'times0': None, 'times1': None,
                               'times2': None, 'times3': None, 'times4': None, 'times5': None,
                               'times6': None, 'times7': None}},
                          power_controller.get_power_modules())

        self.assertEquals(6, power_controller.get_free_address())

    def test_update(self):
        """ Test for updating the power module information. """
        power_controller = self.__get_controller()
        self.assertEquals({}, power_controller.get_power_modules())

        power_controller.register_power_module(1)

        self.assertEquals({1: {'id': 1, 'address': 1, 'name': u'', 'input0': u'', 'input1': u'',
                               'input2': u'', 'input3': u'', 'input4': u'', 'input5': u'',
                               'input6': u'', 'input7': u'', 'sensor0': 0, 'sensor1': 0,
                               'sensor2': 0, 'sensor3': 0, 'sensor4': 0, 'sensor5': 0,
                               'sensor6': 0, 'sensor7': 0, 'times0': None, 'times1': None,
                               'times2': None, 'times3': None, 'times4': None, 'times5': None,
                               'times6': None, 'times7': None}},
                          power_controller.get_power_modules())

        times = ",".join(["00:00" for _ in range(14)])

        power_controller.update_power_module({'id':1, 'name':'module1', 'input0':'in0',
                'input1':'in1', 'input2':'in2', 'input3':'in3', 'input4':'in4', 'input5':'in5',
                'input6':'in6', 'input7':'in7', 'sensor0':0, 'sensor1':1, 'sensor2':2, 'sensor3':3,
                'sensor4':4, 'sensor5':5, 'sensor6':6, 'sensor7':7, 'times0': times,
                'times1': times, 'times2': times, 'times3': times, 'times4': times, 'times5': times,
                'times6': times, 'times7': times})

        self.assertEquals({1: {'id':1, 'address': 1, 'name':'module1', 'input0':'in0',
                'input1':'in1', 'input2':'in2', 'input3':'in3', 'input4':'in4', 'input5':'in5',
                'input6':'in6', 'input7':'in7', 'sensor0':0, 'sensor1':1, 'sensor2':2, 'sensor3':3,
                'sensor4':4, 'sensor5':5, 'sensor6':6, 'sensor7':7, 'times0': times,
                'times1': times, 'times2': times, 'times3': times, 'times4': times, 'times5': times,
                'times6': times, 'times7': times}},
                power_controller.get_power_modules())

    def test_module_exists(self):
        """ Test for module_exists. """
        power_controller = self.__get_controller()

        self.assertFalse(power_controller.module_exists(1))

        power_controller.register_power_module(1)

        self.assertTrue(power_controller.module_exists(1))
        self.assertFalse(power_controller.module_exists(2))

    def test_readdress_power_module(self):
        """ Test for readdress_power_module. """
        power_controller = self.__get_controller()
        power_controller.register_power_module(1)

        power_controller.readdress_power_module(1, 2)

        self.assertFalse(power_controller.module_exists(1))
        self.assertTrue(power_controller.module_exists(2))

        self.assertEquals({1: {'id': 1, 'address': 2, 'name': u'', 'input0': u'', 'input1': u'',
                               'input2': u'', 'input3': u'', 'input4': u'', 'input5': u'',
                               'input6': u'', 'input7': u'', 'sensor0': 0, 'sensor1': 0,
                               'sensor2': 0, 'sensor3': 0, 'sensor4': 0, 'sensor5': 0,
                               'sensor6': 0, 'sensor7': 0, 'times0': None, 'times1': None,
                               'times2': None, 'times3': None, 'times4': None, 'times5': None,
                               'times6': None, 'times7': None}},
                          power_controller.get_power_modules())

    def test_get_address(self):
        """ Test for get_address. """
        power_controller = self.__get_controller()
        self.assertEquals({}, power_controller.get_power_modules())

        power_controller.register_power_module(1)
        power_controller.readdress_power_module(1, 3)

        self.assertEquals(3, power_controller.get_address(1))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
