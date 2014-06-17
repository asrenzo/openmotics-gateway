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
Tests for the scheduling module.

Created on May 23, 2013

@author: fryckbos
'''
import unittest
import time
import os

from gateway.scheduling import SchedulingController

class SchedulingControllerTest(unittest.TestCase):
    """ Tests for SchedulingController. """

    FILE = "test.db"

    def setUp(self): #pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(SchedulingControllerTest.FILE):
            os.remove(SchedulingControllerTest.FILE)

    def tearDown(self): #pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(SchedulingControllerTest.FILE):
            os.remove(SchedulingControllerTest.FILE)

    def __get_controller(self, callback=None, action_timeout=60):
        """ Get a UserController using FILE. """
        if callback == None:
            self.__actions = []
            callback = self.__actions.append

        controller = SchedulingController(SchedulingControllerTest.FILE, callback, action_timeout)
        controller.start()
        return controller

    def test_one(self):
        """ Test executing one action. """
        controller = self.__get_controller()
        now = time.time()

        self.assertEquals(0, len(controller.list_scheduled_actions()))

        controller.schedule_action(now + 1, "Hello action", "ACTION1")

        time.sleep(0.1) # Wait for the background thread to pick up the action.

        actions = controller.list_scheduled_actions()
        self.assertEquals(1, len(actions))
        self.assertEquals(now + 1, actions[0]['timestamp'])
        self.assertEquals("Hello action", actions[0]['description'])
        self.assertEquals("ACTION1", actions[0]['action'])

        time.sleep(1)

        self.assertEquals(0, len(controller.list_scheduled_actions()))

        self.assertEquals(1, len(self.__actions))
        self.assertEquals("ACTION1", self.__actions[0])

        controller.stop()
        controller.close()

    def test_multiple(self):
        """ Test executing multiple actions. """
        controller = self.__get_controller()
        now = time.time()

        controller.schedule_action(now + 1, "My first action", "ACTION1")
        controller.schedule_action(now + 100, "My second action", "ACTION2")

        time.sleep(0.1) # Wait for the background thread to pick up the action.

        actions = controller.list_scheduled_actions()
        self.assertEquals(2, len(actions))

        self.assertEquals(now + 1, actions[0]['timestamp'])
        self.assertEquals("My first action", actions[0]['description'])
        self.assertEquals("ACTION1", actions[0]['action'])

        self.assertEquals(now + 100, actions[1]['timestamp'])
        self.assertEquals("My second action", actions[1]['description'])
        self.assertEquals("ACTION2", actions[1]['action'])

        time.sleep(1)

        actions = controller.list_scheduled_actions()
        self.assertEquals(1, len(actions))

        self.assertEquals(now + 100, actions[0]['timestamp'])
        self.assertEquals("My second action", actions[0]['description'])
        self.assertEquals("ACTION2", actions[0]['action'])

        self.assertEquals(1, len(self.__actions))
        self.assertEquals("ACTION1", self.__actions[0])

        controller.stop()
        controller.close()


    def test_multiple_ordering(self):
        """ Test executing multiple actions in non-insert ordering. """
        controller = self.__get_controller()
        now = time.time()

        controller.schedule_action(now + 100, "My second action", "ACTION2")
        controller.schedule_action(now + 1, "My first action", "ACTION1")

        time.sleep(0.1) # Wait for the background thread to pick up the action.

        actions = controller.list_scheduled_actions()
        self.assertEquals(2, len(actions))

        time.sleep(1)

        actions = controller.list_scheduled_actions()
        self.assertEquals(1, len(actions))

        self.assertEquals(now + 100, actions[0]['timestamp'])
        self.assertEquals("My second action", actions[0]['description'])
        self.assertEquals("ACTION2", actions[0]['action'])

        self.assertEquals(1, len(self.__actions))
        self.assertEquals("ACTION1", self.__actions[0])

        controller.stop()
        controller.close()

    def test_remove(self):
        """ Test removing an actions. """
        controller = self.__get_controller()
        now = time.time()

        controller.schedule_action(now + 100, "My second action", "ACTION2")

        time.sleep(0.1) # Wait for the background thread to pick up the action.

        actions = controller.list_scheduled_actions()
        self.assertEquals(1, len(actions))
        controller.remove_scheduled_action(actions[0]['id'])

        time.sleep(0.1)

        self.assertEquals(0, len(controller.list_scheduled_actions()))

        controller.stop()
        controller.close()

    def test_remove_bad_argument(self):
        """ Test removing a non existing action. """
        controller = self.__get_controller()

        controller.remove_scheduled_action(10)

        time.sleep(1)

        controller.stop()
        controller.close()

    def test_reload(self):
        """ Test reloading the actions on controller restart. """
        controller = self.__get_controller()
        now = time.time()

        controller.schedule_action(now + 100, "My second action", "ACTION2")

        time.sleep(0.1)

        controller.stop()
        controller.close()

        controller = self.__get_controller()

        actions = controller.list_scheduled_actions()
        self.assertEquals(1, len(actions))

        self.assertEquals(now + 100, actions[0]['timestamp'])
        self.assertEquals("My second action", actions[0]['description'])
        self.assertEquals("ACTION2", actions[0]['action'])

        controller.stop()
        controller.close()

    def test_action_timeout(self):
        """ Test timeout on an action that hangs forever. """
        var_dict = {'started' : False, 'done' : False, 'count' : 0}

        def exec_callback(action):
            """ The callback function. """
            var_dict['count'] += 1

            if var_dict['count'] == 2:
                # Check if callback 2 is called before callback 1 is done
                self.assertTrue(var_dict['started'])
                self.assertFalse(var_dict['done'])

            var_dict['started'] = True
            time.sleep(2)
            var_dict['done'] = True

        controller = self.__get_controller(callback=exec_callback, action_timeout=1)
        now = time.time()

        controller.schedule_action(now + 1, "My second action", "ACTION2")
        controller.schedule_action(now + 2, "My second action", "ACTION2")

        time.sleep(2.1)

        self.assertEquals(2, var_dict['count'])

        controller.stop()
        controller.close()

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
