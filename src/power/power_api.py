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
Contains the definition of the power modules Api.

@author: fryckbos
'''

from power.power_command import PowerCommand

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1

def get_general_status():
    """ Get the general status of a power module. """
    return PowerCommand('G', 'GST', '', 'H')

def get_time_on():
    """ Get the time the power module is on (in s) """
    return PowerCommand('G', 'TON', '', 'L')

def get_feed_status():
    """ Get the feed status of the power module (8x 0=low or 1=high) """
    return PowerCommand('G', 'FST', '', '8H')

def get_feed_counter():
    """ Get the feed counter of the power module """
    return PowerCommand('G', 'FCO', '', 'H')

def get_voltage():
    """ Get the voltage of a power module (in V)"""
    return PowerCommand('G', 'VOL', '', 'f')

def get_frequency():
    """ Get the frequency of a power module (in Hz)"""
    return PowerCommand('G', 'FRE', '', 'f')

def get_current():
    """ Get the current of a power module (8x in A)"""
    return PowerCommand('G', 'CUR', '', '8f')

def get_power():
    """ Get the power of a power module (8x in W)"""
    return PowerCommand('G', 'POW', '', '8f')

def get_normal_energy():
    """ Get the total energy measured by the power module (8x in Wh) """
    return PowerCommand('G', 'ENO', '', '8L')

def get_day_energy():
    """ Get the energy measured during the day by the power module (8x in Wh) """
    return PowerCommand('G', 'EDA', '', '8L')

def get_night_energy():
    """ Get the energy measured during the night by the power module (8x in Wh) """
    return PowerCommand('G', 'ENI', '', '8L')

def get_display_timeout():
    """ Get the timeout on the power module display (in min) """
    return PowerCommand('G', 'DTO', '', 'b')

def set_display_timeout():
    """ Set the timeout on the power module display (in min) """
    return PowerCommand('S', 'DTO', '', 'b')

def get_display_screen_menu():
    """ Get the index of the displayed menu on the power module display. """
    return PowerCommand('G', 'DSM', '', 'b')

def set_display_screen_menu():
    """ Set the index of the displayed menu on the power module display. """
    return PowerCommand('S', 'DSM', 'b', '')

def set_day_night():
    """ Set the power module in night (0) or day (1) mode. """
    return PowerCommand('S', 'SDN', '8b', '')

def set_addressmode():
    """ Set the address mode of the power module, 1 = address mode, 0 = normal mode"""
    return PowerCommand('S', 'AGT', 'b', '')

def want_an_address():
    """ The Want An Address command, send by the power modules in address mode. """
    return PowerCommand('S', 'WAA', '', '')

def set_address():
    """ Reply on want_an_address, setting a new address for the power module. """
    return PowerCommand('S', 'SAD', 'b', '')

def get_sensor_types():
    """ Get the sensor types used on the power modules (8x sensor type) """
    return PowerCommand('G', 'CSU', '', '8b')

def set_sensor_types():
    """ Set the sensor types used on the power modules (8x sensor type) """
    return PowerCommand('S', 'CSU', '8b', '')

def get_sensor_names():
    """ Get the names of the available sensor types. """
    return PowerCommand('G', 'CSN', '', '16s16s16s16s16s16s16s16s16s16s')

def set_voltage():
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SVO', 'f', '')


## Below are the function to reset the kwh counters

def reset_normal_energy():
    """ Reset the total energy measured by the power module. """
    return PowerCommand('S', 'ENE', '9B', '')

def reset_day_energy():
    """ Reset the energy measured during the day by the power module. """
    return PowerCommand('S', 'EDA', '9B', '')

def reset_night_energy():
    """ Reset the energy measured during the night by the power module. """
    return PowerCommand('S', 'ENI', '9B', '')


## Below are the bootloader functions

def bootloader_goto():
    """ Go to bootloader and wait for a number of seconds (b parameter) """
    return PowerCommand('S', 'BGT', 'B', '')

def bootloader_read_id():
    """ Get the device id """
    return PowerCommand('G', 'BRI', '', '8B')

def bootloader_write_code():
    """ Write code """
    return PowerCommand('S', 'BWC', '195B', '')

def bootloader_write_configuration():
    """ Write configuration """
    return PowerCommand('S', 'BWF', '24B', '')

def bootloader_jump_application():
    """ Go from bootloader to applications """
    return PowerCommand('S', 'BJA', '', '')

def get_version():
    """ Get the current version of the power module firmware """
    return PowerCommand('G', 'FIV', '', '16s')
