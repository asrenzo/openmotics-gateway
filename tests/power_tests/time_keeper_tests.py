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
Created on Mar 2, 2013

@author: fryckbos
'''
import unittest
from datetime import datetime

from power.time_keeper import TimeKeeper

class PowerControllerDummy(object):
    """ Dummy. """
    pass

class TimeKeeperTest(unittest.TestCase):
    """ Tests for TimeKeeper. """

    def test_is_day_time(self):
        """ Test for is_day_time. """
        tkeep = TimeKeeper(None, PowerControllerDummy(), 10)
        times = \
            "00:10,00:20,00:30,00:40,00:50,01:00,01:10,01:20,01:30,01:40,01:50,02:00,02:10,02:20"

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 4, 0, 0, 0))) # Monday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 4, 0, 10, 0))) # Monday 00:10
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 4, 0, 20, 0))) # Monday 00:20
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 4, 12, 0, 0))) # Monday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 5, 0, 0, 0))) # Tuesday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 5, 0, 30, 0))) # Tuesday 00:30
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 5, 0, 40, 0))) # Tuesday 00:40
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 5, 12, 0, 0))) # Tuesday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 6, 0, 0, 0))) # Wednesday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 6, 0, 50, 0))) # Wednesday 00:50
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 6, 1, 00, 0))) # Wednesday 01:00
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 6, 12, 0, 0))) # Wednesday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 7, 0, 0, 0))) # Thursday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 7, 1, 10, 0))) # Thursday 01:10
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 7, 1, 20, 0))) # Thursday 01:20
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 7, 12, 0, 0))) # Thursday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 8, 0, 0, 0))) # Friday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 8, 1, 30, 0))) # Friday 01:30
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 8, 1, 40, 0))) # Friday 01:40
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 8, 12, 0, 0))) # Friday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 9, 0, 0, 0))) # Saturday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 9, 1, 50, 0))) # Saturday 01:50
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 9, 2, 0, 0))) # Saturday 02:00
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 9, 12, 0, 0))) # Saturday 12:00

        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 10, 0, 0, 0))) # Sunday 00:00
        self.assertTrue(tkeep.is_day_time(times, datetime(2013, 3, 10, 2, 10, 0))) # Sunday 02:10
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 10, 2, 20, 0))) # Sunday 02:20
        self.assertFalse(tkeep.is_day_time(times, datetime(2013, 3, 10, 12, 0, 0))) # Sunday 12:00

        self.assertFalse(tkeep.is_day_time(None, datetime(2013, 3, 10, 0, 0, 0))) # Sunday 00:00
        self.assertFalse(tkeep.is_day_time(None, datetime(2013, 3, 10, 6, 10, 0))) # Sunday 06:00
        self.assertFalse(tkeep.is_day_time(None, datetime(2013, 3, 10, 12, 20, 0))) # Sunday 12:00
        self.assertFalse(tkeep.is_day_time(None, datetime(2013, 3, 10, 18, 0, 0))) # Sunday 18:00

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
