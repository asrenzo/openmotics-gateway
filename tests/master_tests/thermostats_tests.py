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
Created on Feb 24, 2013

@author: fryckbos
'''
import unittest
import time

from master.thermostats import ThermostatStatus

class ThermostatStatusTest(unittest.TestCase):
    """ Tests for ThermostatStatus. """

    def test_should_refresh(self):
        """ Test the should_refresh functionality. """
        status = ThermostatStatus([], 100)
        self.assertFalse(status.should_refresh())

        status.force_refresh()
        self.assertTrue(status.should_refresh())

        status = ThermostatStatus([], 0.001)
        time.sleep(0.01)
        self.assertTrue(status.should_refresh())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
