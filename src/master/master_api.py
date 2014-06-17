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
Contains the definition of the Master Api.
Requires Firmware 3.137.17 -- Caution on update: status api changed (used in update mechanism !)

Created on Sep 9, 2012

@author: fryckbos
'''
from master_command import MasterCommandSpec, Field, OutputFieldType, DimmerFieldType, \
                           ErrorListFieldType

BA_GROUP_ACTION = 2

BA_ALL_SETPOINT_0 = 134
BA_ALL_SETPOINT_1 = 135
BA_ALL_SETPOINT_2 = 136
BA_ALL_SETPOINT_3 = 137
BA_ALL_SETPOINT_4 = 138
BA_ALL_SETPOINT_5 = 139
BA_THERMOSTAT_MODE = 140
BA_THERMOSTAT_AUTOMATIC = 141

BA_LIGHT_OFF = 160
BA_LIGHT_ON = 161
BA_LIGHT_TOGGLE = 162
BA_ALL_LIGHTS_OFF = 163
BA_ALL_OUTPUTS_OFF = 164
BA_LIGHT_ON_DIMMER_MIN = 165
BA_LIGHT_ON_DIMMER_MAX = 166
BA_LIGHT_ON_DIMMER_PLUS_5 = 167
BA_LIGHTS_ON_DIMMER_MIN_5 = 168
BA_DIMMER_MIN = 169
BA_DIMMER_MAX = 170
BA_LIGHTS_OFF_FLOOR = 171
BA_LIGHTS_ON_FLOOR = 172
BA_LIGHTS_TOGGLE_FLOOR = 173
BA_LIGHT_ON_DIMMER_10 = 176
BA_LIGHT_ON_DIMMER_20 = 177
BA_LIGHT_ON_DIMMER_30 = 178
BA_LIGHT_ON_DIMMER_40 = 179
BA_LIGHT_ON_DIMMER_50 = 180
BA_LIGHT_ON_DIMMER_60 = 181
BA_LIGHT_ON_DIMMER_70 = 182
BA_LIGHT_ON_DIMMER_80 = 183
BA_LIGHT_ON_DIMMER_90 = 184
BA_LIGHT_TOGGLE_DIMMER_10 = 185
BA_LIGHT_TOGGLE_DIMMER_20 = 186
BA_LIGHT_TOGGLE_DIMMER_30 = 187
BA_LIGHT_TOGGLE_DIMMER_40 = 188
BA_LIGHT_TOGGLE_DIMMER_50 = 189
BA_LIGHT_TOGGLE_DIMMER_60 = 190
BA_LIGHT_TOGGLE_DIMMER_70 = 191
BA_LIGHT_TOGGLE_DIMMER_80 = 192
BA_LIGHT_TOGGLE_DIMMER_90 = 193
BA_LIGHT_TOGGLE_DIMMER_100 = 194
BA_LIGHT_ON_TIMER_150_OVERRULE = 195
BA_LIGHT_ON_TIMER_450_OVERRULE = 196
BA_LIGHT_ONT_TIMER_900_OVERRULE = 197
BA_LIGHT_ON_TIMER_1500_OVERRULE = 198
BA_LIGHT_ON_TIMER_2220_OVERRULE = 199
BA_LIGHT_ON_TIMER_3120_OVERRULE = 200
BA_LIGHT_ON_TIMER_150_NO_OVERRULE = 201
BA_LIGHT_ON_TIMER_450_NO_OVERRULE = 202
BA_LIGHT_ONT_TIMER_900_NO_OVERRULE = 203
BA_LIGHT_ON_TIMER_1500_NO_OVERRULE = 204
BA_LIGHT_ON_TIMER_2220_NO_OVERRULE = 205
BA_LIGHT_ON_TIMER_3120_NO_OVERRULE = 206

BA_STATUS_LEDS = 64

def basic_action():
    """ Basic actions. """
    return MasterCommandSpec("BA",
        [Field.byte("action_type"), Field.byte("action_number"), Field.padding(11)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

def reset():
    """ Reset the gateway, used for firmware updates. """
    return MasterCommandSpec("re",
        [Field.padding(13)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

def status():
    """ Get the status of the master. """
    return MasterCommandSpec("ST",
        [Field.padding(13)],
        [Field.byte('seconds'), Field.byte('minutes'), Field.byte('hours'), Field.byte('weekday'),
         Field.byte('day'), Field.byte('month'), Field.byte('year'), Field.lit('\x00'),
         Field.byte('mode'), Field.byte('f1'), Field.byte('f2'), Field.byte('f3'),
         Field.byte('h'), Field.lit('\r\n')])

def set_time():
    """ Set the time on the master. """
    return MasterCommandSpec("st",
        [Field.byte('sec'), Field.byte('min'), Field.byte('hours'), Field.byte('weekday'),
         Field.byte('day'), Field.byte('month'), Field.byte('year'), Field.padding(6)],
        [Field.byte('sec'), Field.byte('min'), Field.byte('hours'), Field.byte('weekday'),
         Field.byte('day'), Field.byte('month'), Field.byte('year'), Field.padding(6),
         Field.lit("\r\n")])

def eeprom_list():
    """ List all bytes from a certain eeprom bank """
    return MasterCommandSpec("EL",
        [Field.byte("bank"), Field.padding(12)],
        [Field.byte("bank"), Field.str("data", 256), Field.lit("\r\n")])

def read_eeprom():
    """ Read a number (1-10) of bytes from a certain eeprom bank and address. """
    return MasterCommandSpec("RE",
        [Field.byte('bank'), Field.byte('addr'), Field.byte('num'), Field.padding(10)],
        [Field.byte('bank'), Field.byte('addr'), Field.varstr('data', 10), Field.lit('\r\n')])

def write_eeprom():
    """ Write data bytes to the addr in the specified eeprom bank """
    return MasterCommandSpec("WE",
        [Field.byte("bank"), Field.byte("address"), Field.varstr("data", 10)],
        [Field.byte("bank"), Field.byte("address"), Field.varstr("data", 10), Field.lit('\r\n')])

def activate_eeprom():
    """ Activate eeprom after write """
    return MasterCommandSpec("AE",
        [Field.byte("eep"), Field.padding(12)],
        [Field.byte("eep"), Field.str("resp", 2), Field.padding(10), Field.lit('\r\n')])

def number_of_io_modules():
    """ Read the number of input and output modules """
    return MasterCommandSpec("rn",
        [Field.padding(13)],
        [Field.byte("in"), Field.byte("out"), Field.padding(11), Field.lit('\r\n')])

def read_output():
    """ Read the information about an output """
    return MasterCommandSpec("ro",
        [Field.byte("id"), Field.padding(12)],
        [Field.byte('id'), Field.str('type', 1), Field.byte('light'), Field.int('timer'),
         Field.int('ctimer'), Field.byte('status'), Field.dimmer('dimmer'),
         Field.byte('controller_out'), Field.byte('max_power'), Field.byte('floor_level'),
         Field.bytes('menu_position', 3), Field.str('name', 16), Field.crc(),
         Field.lit('\r\n')])

def read_input():
    """ Read the information about an input """
    return MasterCommandSpec("ri",
        [Field.byte("input_nr"), Field.padding(12)],
        [Field.byte('input_nr'), Field.byte('output_action'), Field.bytes('output_list', 30),
         Field.str('input_name', 8), Field.crc(), Field.lit('\r\n')])

def temperature_list():
    """ Read the temperature thermostat sensor list for a series of 12 sensors """
    return MasterCommandSpec("TL",
        [Field.byte("series"), Field.padding(12)],
        [Field.byte("series"), Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'),
         Field.svt('tmp3'), Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'),
         Field.svt('tmp7'), Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'),
         Field.svt('tmp11'), Field.lit('\r\n')])

def setpoint_list():
    """ Read the current setpoint of the thermostats in series of 12 """
    return MasterCommandSpec("SL",
        [Field.byte("series"), Field.padding(12)],
        [Field.byte("series"), Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'),
         Field.svt('tmp3'), Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'),
         Field.svt('tmp7'), Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'),
         Field.svt('tmp11'), Field.lit('\r\n')])

def thermostat_mode():
    """ Read the current thermostat mode """
    return MasterCommandSpec("TM",
        [Field.padding(13)],
        [Field.byte('mode'), Field.padding(12), Field.lit('\r\n')])

def read_setpoint():
    """ Read the programmed setpoint of a thermostat """
    return MasterCommandSpec("rs",
        [Field.byte('thermostat'), Field.padding(12)],
        [Field.byte('thermostat'), Field.svt('act'), Field.svt('csetp'), Field.svt('psetp0'),
         Field.svt('psetp1'), Field.svt('psetp2'), Field.svt('psetp3'), Field.svt('psetp4'),
         Field.svt('psetp5'), Field.byte('sensor_nr'), Field.byte('output0_nr'),
         Field.byte('output1_nr'), Field.byte('output0'), Field.byte('output1'),
         Field.svt('outside'), Field.byte('mode'), Field.str('name', 16), Field.byte('pid_p'),
         Field.byte('pid_i'), Field.byte('pid_d'), Field.byte('pid_ithresh'),
         Field.svt('threshold_temp'), Field.byte('days'), Field.byte('hours'),
         Field.byte('minutes'), Field.svt('mon_start_d1'), Field.svt('mon_stop_d1'),
         Field.svt('mon_start_d2'), Field.svt('mon_stop_d2'), Field.svt('tue_start_d1'),
         Field.svt('tue_stop_d1'), Field.svt('tue_start_d2'), Field.svt('tue_stop_d2'),
         Field.svt('wed_start_d1'), Field.svt('wed_stop_d1'), Field.svt('wed_start_d2'),
         Field.svt('wed_stop_d2'), Field.svt('thu_start_d1'), Field.svt('thu_stop_d1'),
         Field.svt('thu_start_d2'), Field.svt('thu_stop_d2'), Field.svt('fri_start_d1'),
         Field.svt('fri_stop_d1'), Field.svt('fri_start_d2'), Field.svt('fri_stop_d2'),
         Field.svt('sat_start_d1'), Field.svt('sat_stop_d1'), Field.svt('sat_start_d2'),
         Field.svt('sat_stop_d2'), Field.svt('sun_start_d1'), Field.svt('sun_stop_d1'),
         Field.svt('sun_start_d2'), Field.svt('sun_stop_d2'), Field.lit('T'),
         Field.svt('mon_temp_d1'), Field.svt('tue_temp_d1'), Field.svt('wed_temp_d1'),
         Field.svt('thu_temp_d1'), Field.svt('fri_temp_d1'), Field.svt('sat_temp_d1'),
         Field.svt('sun_temp_d1'), Field.svt('mon_temp_d2'), Field.svt('tue_temp_d2'),
         Field.svt('wed_temp_d2'), Field.svt('thu_temp_d2'), Field.svt('fri_temp_d2'),
         Field.svt('sat_temp_d2'), Field.svt('sun_temp_d2'), Field.svt('mon_temp_n'),
         Field.svt('tue_temp_n'), Field.svt('wed_temp_n'), Field.svt('thu_temp_n'),
         Field.svt('fri_temp_n'), Field.svt('sat_temp_n'), Field.svt('sun_temp_n'),
         Field.crc(), Field.lit('\r\n')])

def write_setpoint():
    """ Write a setpoints of a thermostats """
    return MasterCommandSpec("ws",
        [Field.byte("thermostat"), Field.byte("config"), Field.svt("temp"), Field.padding(10)],
        [Field.byte("thermostat"), Field.byte("config"), Field.svt("temp"), Field.padding(10),
         Field.lit('\r\n')])

def thermostat_list():
    """ Read the thermostat mode, the outside temperature, the temperature of each thermostat,
    as well as the setpoint.
    """
    return MasterCommandSpec("tl",
        [Field.padding(13)],
        [Field.byte('mode'), Field.svt('outside'),
         Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'), Field.svt('tmp3'),
         Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'), Field.svt('tmp7'),
         Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'), Field.svt('tmp11'),
         Field.svt('tmp12'), Field.svt('tmp13'), Field.svt('tmp14'), Field.svt('tmp15'),
         Field.svt('tmp16'), Field.svt('tmp17'), Field.svt('tmp18'), Field.svt('tmp19'),
         Field.svt('tmp20'), Field.svt('tmp21'), Field.svt('tmp22'), Field.svt('tmp23'),
         Field.svt('setp0'), Field.svt('setp1'), Field.svt('setp2'), Field.svt('setp3'),
         Field.svt('setp4'), Field.svt('setp5'), Field.svt('setp6'), Field.svt('setp7'),
         Field.svt('setp8'), Field.svt('setp9'), Field.svt('setp10'), Field.svt('setp11'),
         Field.svt('setp12'), Field.svt('setp13'), Field.svt('setp14'), Field.svt('setp15'),
         Field.svt('setp16'), Field.svt('setp17'), Field.svt('setp18'), Field.svt('setp19'),
         Field.svt('setp20'), Field.svt('setp21'), Field.svt('setp22'), Field.svt('setp23'),
         Field.crc(), Field.lit('\r\n')])

def sensor_humidity_list():
    """ Reads the list humidity values of the 32 (0-31) sensors. """
    return MasterCommandSpec("hl",
        [Field.padding(13)],
        [Field.hum('hum0'), Field.hum('hum1'), Field.hum('hum2'), Field.hum('hum3'),
         Field.hum('hum4'), Field.hum('hum5'), Field.hum('hum6'), Field.hum('hum7'),
         Field.hum('hum8'), Field.hum('hum9'), Field.hum('hum10'), Field.hum('hum11'),
         Field.hum('hum12'), Field.hum('hum13'), Field.hum('hum14'), Field.hum('hum15'),
         Field.hum('hum16'), Field.hum('hum17'), Field.hum('hum18'), Field.hum('hum19'),
         Field.hum('hum20'), Field.hum('hum21'), Field.hum('hum22'), Field.hum('hum23'),
         Field.hum('hum24'), Field.hum('hum25'), Field.hum('hum26'), Field.hum('hum27'),
         Field.hum('hum28'), Field.hum('hum29'), Field.hum('hum30'), Field.hum('hum31'),
         Field.crc(), Field.lit('\r\n')])

def sensor_temperature_list():
    """ Reads the list temperature values of the 32 (0-31) sensors. """
    return MasterCommandSpec("cl",
        [Field.padding(13)],
        [Field.svt('tmp0'), Field.svt('tmp1'), Field.svt('tmp2'), Field.svt('tmp3'),
         Field.svt('tmp4'), Field.svt('tmp5'), Field.svt('tmp6'), Field.svt('tmp7'),
         Field.svt('tmp8'), Field.svt('tmp9'), Field.svt('tmp10'), Field.svt('tmp11'),
         Field.svt('tmp12'), Field.svt('tmp13'), Field.svt('tmp14'), Field.svt('tmp15'),
         Field.svt('tmp16'), Field.svt('tmp17'), Field.svt('tmp18'), Field.svt('tmp19'),
         Field.svt('tmp20'), Field.svt('tmp21'), Field.svt('tmp22'), Field.svt('tmp23'),
         Field.svt('tmp24'), Field.svt('tmp25'), Field.svt('tmp26'), Field.svt('tmp27'),
         Field.svt('tmp28'), Field.svt('tmp29'), Field.svt('tmp30'), Field.svt('tmp31'),
         Field.crc(), Field.lit('\r\n')])

def sensor_brightness_list():
    """ Reads the list brightness values of the 32 (0-31) sensors. """
    return MasterCommandSpec("bl",
        [Field.padding(13)],
        [Field.byte('bri0'), Field.byte('bri1'), Field.byte('bri2'), Field.byte('bri3'),
         Field.byte('bri4'), Field.byte('bri5'), Field.byte('bri6'), Field.byte('bri7'),
         Field.byte('bri8'), Field.byte('bri9'), Field.byte('bri10'), Field.byte('bri11'),
         Field.byte('bri12'), Field.byte('bri13'), Field.byte('bri14'), Field.byte('bri15'),
         Field.byte('bri16'), Field.byte('bri17'), Field.byte('bri18'), Field.byte('bri19'),
         Field.byte('bri20'), Field.byte('bri21'), Field.byte('bri22'), Field.byte('bri23'),
         Field.byte('bri24'), Field.byte('bri25'), Field.byte('bri26'), Field.byte('bri27'),
         Field.byte('bri28'), Field.byte('bri29'), Field.byte('bri30'), Field.byte('bri31'),
         Field.crc(), Field.lit('\r\n')])

def pulse_list():
    """ List the pulse counter values. """
    return MasterCommandSpec("PL",
        [Field.padding(13)],
        [Field.int('pv0'), Field.int('pv1'), Field.int('pv2'), Field.int('pv3'), Field.int('pv4'),
         Field.int('pv5'), Field.int('pv6'), Field.int('pv7'), Field.lit('\r\n')])

def error_list():
    """ Get the number of errors for each input and output module. """
    return MasterCommandSpec("el",
        [Field.padding(13)],
        [Field("errors", ErrorListFieldType()), Field.crc(), Field.lit("\r\n")])

def clear_error_list():
    """ Clear the number of errors. """
    return MasterCommandSpec("ec",
        [Field.padding(13)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

def to_cli_mode():
    """ Go to CLI mode """
    return MasterCommandSpec("CM",
        [Field.padding(13)],
        None)

def module_discover_start():
    """ Put the master in module discovery mode. """
    return MasterCommandSpec("DA",
        [Field.padding(13)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

def module_discover_stop():
    """ Put the master into the normal working state. """
    return MasterCommandSpec("DO",
        [Field.padding(13)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

def indicate():
    """ Flash the led for a given output/input/sensor. """
    return MasterCommandSpec("IN",
        [Field.byte('type'), Field.byte('id'), Field.padding(11)],
        [Field.str("resp", 2), Field.padding(11), Field.lit("\r\n")])

### Below are the asynchronous messages, sent by the master to the gateway

def output_list():
    """ The message sent by the master whenever the outputs change. """
    return MasterCommandSpec("OL",
        [],
        [Field("outputs", OutputFieldType()), Field.lit("\r\n")])

def input_list():
    """ The message sent by the master whenever an input is enabled. """
    return MasterCommandSpec("IL",
        [],
        [Field.byte('input'), Field.byte('output'), Field.lit("\r\n")])

def module_initialize():
    """ The message sent by the master whenever a module is initialized in module discovery mode.
    """
    return MasterCommandSpec("MI",
        [],
        [Field.str('id', 4), Field.str('instr', 1), Field.byte('module_nr'), Field.byte('data'),
         Field.padding(6), Field.lit('\r\n')])

### Below are the function to update the firmware of the modules (input/output/dimmer/thermostat)

def modules_goto_bootloader():
    """ Reset the module to go to the bootloader. """
    return MasterCommandSpec("FR",
        [Field.str('addr', 4), Field.byte('sec'), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.padding(5)],
        [Field.str('addr', 4), Field.byte("error_code"), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.padding(5), Field.lit("\r\n")])

def modules_new_firmware_version():
    """ Preprare the slave module for a new version. """
    return MasterCommandSpec("FN",
        [Field.str('addr', 4), Field.byte("f1n"), Field.byte("f2n"), Field.byte("f3n"),
         Field.lit('C'), Field.byte('crc0'), Field.byte('crc1'), Field.padding(3)],
        [Field.str('addr', 4), Field.byte("error_code"), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.padding(5), Field.lit("\r\n")])

def modules_new_crc():
    """ Write the new crc code to the bootloaded module. """
    return MasterCommandSpec("FC",
        [Field.str('addr', 4), Field.byte("ccrc0"), Field.byte("ccrc1"), Field.byte("ccrc2"),
         Field.byte("ccrc3"), Field.lit('C'), Field.byte('crc0'), Field.byte('crc1'),
         Field.padding(2)],
        [Field.str('addr', 4), Field.byte("error_code"), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.padding(5), Field.lit("\r\n")])

def change_communication_mode_to_long():
    """ Change the number of bytes used to communicate with the master to 75. """
    return MasterCommandSpec("cm",
        [Field.lit('\x4d'), Field.lit('\x01'), Field.padding(11)],
        [Field.lit('\x4d'), Field.lit('\x01'), Field.padding(11), Field.lit("\r\n")])

def change_communication_mode_to_short():
    """ Change the number of bytes used to communicate with the master to 18. """
    return MasterCommandSpec("cm",
        [Field.lit('\x12'), Field.lit('\x00'), Field.padding(71)],
        [Field.lit('\x12'), Field.lit('\x00'), Field.padding(11), Field.lit("\r\n")])

def modules_update_firmware_block():
    """ Upload 1 block of 64 bytes to the module. """
    return MasterCommandSpec("FD",
        [Field.str('addr', 4), Field.int("block"), Field.str("bytes", 64),
         Field.lit('C'), Field.byte('crc0'), Field.byte('crc1')],
        [Field.str('addr', 4), Field.byte("error_code"), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.lit("\r\n")])

def modules_verify_firmware():
    """ Tell the master to verify the update firmware. """
    return MasterCommandSpec("FV",
        [Field.str('addr', 4), Field.lit('C'), Field.byte('crc0'), Field.byte('crc1'),
         Field.padding(6)],
        [Field.str('addr', 4), Field.byte("error_code"), Field.byte("hw_version"),
         Field.byte("f1"), Field.byte("f2"), Field.byte("f3"), Field.byte("status"),
         Field.lit('C'), Field.byte('crc0'), Field.byte('crc1'), Field.lit("\r\n")])

def modules_goto_application():
    """ Let the module go to application. """
    return MasterCommandSpec("FG",
        [Field.str('addr', 4), Field.lit('C'), Field.byte('crc0'), Field.byte('crc1'),
         Field.padding(6)],
        [Field.str('addr', 4), Field.byte("error_code"), Field.lit('C'), Field.byte('crc0'),
         Field.byte('crc1'), Field.padding(5), Field.lit("\r\n")])


### Below are helpers for the Svt (System value type).

class Svt(object):
    """ Class for the system value type, this can be either a time or a temperature. """
    TIME = 1
    TEMPERATURE = 2
    RAW = 3

    def __init__(self, type, value):
        """ Default constructor.
        :param type: Type of the Svt (can be Svt.TIME or Svt.TERMPERATUR).
        """
        if type == Svt.TIME:
            split = [int(x) for x in value.split(":")]
            if len(split) != 2:
                raise ValueError("Time is not in HH:MM format: %s" % value)
            self.__value = (split[0] * 6) + (split[1] / 10)
        elif type == Svt.TEMPERATURE:
            self.__value = int((value + 32) * 2)
        elif type == Svt.RAW:
            self.__value = value
        else:
            raise ValueError("Unknown type for Svt: " + str(type))

    def get_time(self):
        """ Convert an Svt to time.
        :returns: String with form HH:MM
        """
        hours = (self.__value / 6)
        minutes = (self.__value % 6) * 10
        return "%02d:%02d" % (hours, minutes)

    def get_temperature(self):
        """ Convert an Svt to temperature.
        :returns: degrees celcius (float).
        """
        return (float(self.__value) / 2) - 32

    def get_byte(self):
        """ Get the Svt value as a byte.
        :returns: one byte
        """
        return chr(self.__value)

    @staticmethod
    def from_byte(byte_value):
        """ Create an Svt instance from a byte.
        :returns: instance of the Svt class.
        """
        return Svt(Svt.RAW, ord(byte_value))

    @staticmethod
    def temp(temperature):
        """ Create an Svt instance from a temperature.
        :param temperature: in degrees celcius (float)
        """
        return Svt(Svt.TEMPERATURE, temperature)

    @staticmethod
    def time(time_value):
        """ Create an Svt instance from a time value.
        :param time_value: String in format HH:MM
        """
        return Svt(Svt.TIME, time_value)

def dimmer_to_percentage(dimmer_value):
    """ Convert a dimmer value to an integer in [0, 100].

    :param dimmer_value: integer in [0, 63].
    :returns: dimmer percentage in [0, 100].
    """
    return DimmerFieldType().decode(chr(dimmer_value))
