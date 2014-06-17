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
Tests for the users module.

Created on Sep 22, 2012

@author: fryckbos
'''
import unittest
import time
import os

from gateway.users import UserController

class UserControllerTest(unittest.TestCase):
    """ Tests for UserController. """

    FILE = "test.db"

    def setUp(self): #pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(UserControllerTest.FILE):
            os.remove(UserControllerTest.FILE)

    def tearDown(self): #pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(UserControllerTest.FILE):
            os.remove(UserControllerTest.FILE)

    def __get_controller(self):
        """ Get a UserController using FILE. """
        return UserController(UserControllerTest.FILE,
                              {'username' : 'om', 'password' : 'pass'}, 10)

    def test_empty(self):
        """ Test an empty database. """
        user_controller = self.__get_controller()
        self.assertEquals(None, user_controller.login("fred", "test"))
        self.assertEquals(False, user_controller.check_token("some token 123"))
        self.assertEquals(None, user_controller.get_role("fred"))

        token = user_controller.login("om", "pass")
        self.assertNotEquals(None, token)

        self.assertTrue(user_controller.check_token(token))

    def test_all(self):
        """ Test all methods of UserController. """
        user_controller = self.__get_controller()
        user_controller.create_user("fred", "test", "admin", True)

        self.assertEquals(None, user_controller.login("fred", "123"))
        self.assertFalse(user_controller.check_token("blah"))

        token = user_controller.login("fred", "test")
        self.assertNotEquals(None, token)

        self.assertTrue(user_controller.check_token(token))
        self.assertFalse(user_controller.check_token("blah"))

        self.assertEquals("admin", user_controller.get_role("fred"))

    def test_token_timeout(self):
        """ Test the timeout on the tokens. """
        user_controller = UserController(UserControllerTest.FILE,
                              {'username' : 'om', 'password' : 'pass'}, 3)

        token = user_controller.login("om", "pass")
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

        time.sleep(4)

        self.assertFalse(user_controller.check_token(token))

        token = user_controller.login("om", "pass")
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

    def test_timeout(self):
        """ Test logout. """
        user_controller = UserController(UserControllerTest.FILE,
                              {'username' : 'om', 'password' : 'pass'}, 3)

        token = user_controller.login("om", "pass")
        self.assertNotEquals(None, token)
        self.assertTrue(user_controller.check_token(token))

        user_controller.logout(token)
        self.assertFalse(user_controller.check_token(token))       

    def test_get_usernames(self):
        """ Test getting all usernames. """
        user_controller = self.__get_controller()
        self.assertEquals(["om"], user_controller.get_usernames())

        user_controller.create_user("test", "test", "admin", True)
        self.assertEquals(["om", "test"], user_controller.get_usernames())

    def test_remove_user(self):
        """ Test removing a user. """
        user_controller = self.__get_controller()
        self.assertEquals(["om"], user_controller.get_usernames())

        user_controller.create_user("test", "test", "admin", True)

        token = user_controller.login("test", "test")
        self.assertTrue(user_controller.check_token(token))

        user_controller.remove_user("test")

        self.assertFalse(user_controller.check_token(token))
        self.assertEquals(["om"], user_controller.get_usernames())

        try:
            user_controller.remove_user("om")
            self.fail("Should have raised exception !")
        except Exception as exception:
            self.assertEquals("Cannot delete last admin account", str(exception))

    def test_case_insensitive(self):
        """ Test the case insensitivity of the username. """
        user_controller = self.__get_controller()

        user_controller.create_user("TEST", "test", "admin", True)

        token = user_controller.login("test", "test")
        self.assertTrue(user_controller.check_token(token))

        token = user_controller.login("TesT", "test")
        self.assertTrue(user_controller.check_token(token))

        self.assertEquals(None, user_controller.login("test", "Test"))

        self.assertEquals(["om", "test"], user_controller.get_usernames())

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
