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
import time

class ThermostatStatus(object):
    """ Contains a cached version of the current thermostat status. """

    def __init__(self, thermostats, refresh_period=600):
        """ Create a status object using a list of thermostats (can be None),
        and a refresh period: the refresh has to be invoked explicitly. """
        self.__thermostats = thermostats
        self.__refresh_period = refresh_period
        self.__last_refresh = time.time()

    def force_refresh(self):
        """ Force a refresh on the ThermostatStatus. """
        self.__last_refresh = 0

    def should_refresh(self):
        """ Check whether the status should be refreshed. """
        return time.time() >= self.__last_refresh + self.__refresh_period

    def update(self, thermostats):
        """ Update the status of the thermostats using a list of thermostats. """
        self.__thermostats = thermostats
        self.__last_refresh = time.time()

    def get_thermostats(self):
        """ Return the list of thermostats. """
        return self.__thermostats
