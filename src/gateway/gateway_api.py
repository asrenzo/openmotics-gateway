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
The GatewayApi defines high level functions, these are used by the interface
and call the master_api to complete the actions.

Created on Sep 16, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import time as pytime
import datetime
import traceback
import math
from threading import Timer

from serial_utils import CommunicationTimedOutException

import master.master_api as master_api
from master.outputs import OutputStatus
from master.inputs import InputStatus
from master.thermostats import ThermostatStatus
from master.master_communicator import BackgroundConsumer

from master.eeprom_controller import EepromController, EepromFile
from master.eeprom_models import OutputConfiguration, InputConfiguration, ThermostatConfiguration,\
              SensorConfiguration, PumpGroupConfiguration, GroupActionConfiguration, \
              ScheduledActionConfiguration, PulseCounterConfiguration, StartupActionConfiguration,\
              DimmerConfiguration, GlobalThermostatConfiguration

import power.power_api as power_api

def convert_nan(number):
    """ Convert nan to 0. """
    return 0.0 if math.isnan(number) else number

class GatewayApi(object):
    """ The GatewayApi combines master_api functions into high level functions. """

    def __init__(self, master_communicator, power_communicator, power_controller):
        self.__master_communicator = master_communicator

        self.__last_maintenance_send_time = 0
        self.__maintenance_timeout_timer = None

        self.__discover_mode_timer = None

        self.__output_status = None
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.output_list(), 0, self.__update_outputs))

        self.__input_status = InputStatus()
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.input_list(), 0, self.__update_inputs))

        self.__module_log = []
        self.__master_communicator.register_consumer(
                    BackgroundConsumer(master_api.module_initialize(), 0, self.__update_modules))

        self.__thermostat_status = None

        self.__eeprom_controller = EepromController(EepromFile(self.__master_communicator))

        self.__power_communicator = power_communicator
        self.__power_controller = power_controller

        self.__plugin_controller = None

        self.init_master()
        self.__run_master_timer()

    def set_plugin_controller(self, plugin_controller):
        """ Set the plugin controller. """
        self.__plugin_controller = plugin_controller

    def init_master(self):
        """ Initialize the master: disable the async RO messages, enable async OL messages. """
        try:
            eeprom_data = self.__master_communicator.do_command(master_api.eeprom_list(),
                {"bank" : 0})['data']

            write = False

            if eeprom_data[11] != chr(255):
                LOGGER.info("Disabling async RO messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    {"bank" : 0, "address": 11, "data": chr(255)})
                write = True

            if eeprom_data[18] != chr(0):
                LOGGER.info("Enabling async OL messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    {"bank" : 0, "address": 18, "data": chr(0)})
                write = True

            if eeprom_data[20] != chr(0):
                LOGGER.info("Enabling async IL messages.")
                self.__master_communicator.do_command(master_api.write_eeprom(),
                    {"bank" : 0, "address": 20, "data": chr(0)})
                write = True

            if write:
                self.__master_communicator.do_command(master_api.activate_eeprom(), {'eep' : 0})

        except CommunicationTimedOutException:
            LOGGER.error("Got CommunicationTimedOutException during gateway_api initialization.")

    def __run_master_timer(self):
        """ Run the master timer, this sets the masters clock if it differs more than 3 minutes
        from the gateway clock. """

        try:
            status = self.__master_communicator.do_command(master_api.status())
            date = "%02d.%02d.%02d %02d:%02d:%02d" % (status['day'], status['month'],
                        status['year'], status['hours'], status['minutes'], status['seconds'])

            epoch_master = pytime.mktime(pytime.strptime(date, "%d.%m.%y %H:%M:%S"))
            epoch_gateway = pytime.time()

            if abs(epoch_master - epoch_gateway) > 180: # Allow 3 minutes slack
                self.sync_master_time()

        except:
            LOGGER.error("Got error while setting the time on the master.")
            traceback.print_exc()
        finally:
            Timer(120, self.__run_master_timer).start()

    def sync_master_time(self):
        """ Set the time on the master. """
        LOGGER.info("Setting the time on the master.")
        now = datetime.datetime.now()
        self.__master_communicator.do_command(master_api.set_time(),
                  {'sec': now.second, 'min': now.minute, 'hours': now.hour,
                   'weekday': now.isoweekday(), 'day': now.day, 'month': now.month,
                   'year': now.year % 100})

    ###### Maintenance functions

    def start_maintenance_mode(self, timeout=600):
        """ Start maintenance mode, if the time between send_maintenance_data calls exceeds the
        timeout, the maintenance mode will be closed automatically. """
        try:
            self.set_master_status_leds(True)
        except Exception as exception:
            msg = "Exception while setting status leds before maintenance mode:" + str(exception)
            LOGGER.warning(msg)

        self.__eeprom_controller.invalidate_cache() # Eeprom can be changed in maintenance mode.
        self.__master_communicator.start_maintenance_mode()

        def check_maintenance_timeout():
            """ Checks if the maintenance if the timeout is exceeded, and closes maintenance mode
            if required. """
            if self.__master_communicator.in_maintenance_mode():
                current_time = pytime.time()
                if self.__last_maintenance_send_time + timeout < current_time:
                    LOGGER.info("Stopping maintenance mode because of timeout.")
                    self.stop_maintenance_mode()
                else:
                    wait_time = self.__last_maintenance_send_time + timeout - current_time
                    self.__maintenance_timeout_timer = Timer(wait_time, check_maintenance_timeout)
                    self.__maintenance_timeout_timer.start()

        self.__maintenance_timeout_timer = Timer(timeout, check_maintenance_timeout)
        self.__maintenance_timeout_timer.start()


    def send_maintenance_data(self, data):
        """ Send data to the master in maintenance mode.

        :param data: data to send to the master
        :type data: string
        """
        self.__last_maintenance_send_time = pytime.time()
        self.__master_communicator.send_maintenance_data(data)

    def get_maintenance_data(self):
        """ Get data from the master in maintenance mode.

        :returns: string containing unprocessed output
        """
        return self.__master_communicator.get_maintenance_data()

    def stop_maintenance_mode(self):
        """ Stop maintenance mode. """
        self.__master_communicator.stop_maintenance_mode()
        if self.__output_status != None:
            self.__output_status.force_refresh()

        if self.__thermostat_status != None:
            self.__thermostat_status.force_refresh()

        if self.__maintenance_timeout_timer != None:
            self.__maintenance_timeout_timer.cancel()
            self.__maintenance_timeout_timer = None

        try:
            self.set_master_status_leds(False)
        except Exception as exception:
            msg = "Exception while setting status leds after maintenance mode:" + str(exception)
            LOGGER.warning(msg)

    def get_status(self):
        """ Get the status of the Master.

        :returns: dict with 'time' (HH:MM), 'date' (DD:MM:YYYY), 'mode', 'version' (a.b.c)
                  and 'hw_version' (hardware version)
        """
        out_dict = self.__master_communicator.do_command(master_api.status())
        return {'time' : '%02d:%02d' % (out_dict['hours'], out_dict['minutes']),
                'date' : '%02d/%02d/%d' % (out_dict['day'], out_dict['month'], out_dict['year']),
                'mode' : out_dict['mode'],
                'version' : "%d.%d.%d" % (out_dict['f1'], out_dict['f2'], out_dict['f3']),
                'hw_version' : out_dict['h']}

    def reset_master(self):
        """ Perform a cold reset on the master. Turns the power off, waits 5 seconds and
        turns the power back on.

        :returns: 'status': 'OK'.
        """
        gpio_direction = open('/sys/class/gpio/gpio44/direction', 'w')
        gpio_direction.write('out')
        gpio_direction.close()

        def power(master_on):
            """ Set the power on the master. """
            gpio_file = open('/sys/class/gpio/gpio44/value', 'w')
            gpio_file.write('1' if master_on else '0')
            gpio_file.close()

        power(False)
        pytime.sleep(5)
        power(True)

        return {'status' : 'OK'}

    ###### Master module functions

    def __update_modules(self, api_data):
        """ Create a log entry when the MI message is received. """
        module_map = {'O' : 'output', 'I' : 'input', 'T' : 'temperature', 'D' : 'dimmer'}
        message_map = {'N' : 'New %s module found.',
                       'E' : 'Existing %s module found.',
                       'D' : 'The %s module tried to register but the registration failed, '
                             'please presse the init button again.'}
        log_level_map = {'N' : 'INFO', 'E' : 'WARN', 'D' : 'ERROR'}

        module_type = module_map.get(api_data['id'][0])
        message = message_map.get(api_data['instr']) % module_type
        log_level = log_level_map.get(api_data['instr'])

        self.__module_log.append((log_level, message))

    def module_discover_start(self, timeout=900):
        """ Start the module discover mode on the master.

        :returns: dict with 'status' ('OK').
        """
        ret = self.__master_communicator.do_command(master_api.module_discover_start())

        if self.__discover_mode_timer != None:
            self.__discover_mode_timer.cancel()

        self.__discover_mode_timer = Timer(timeout, self.module_discover_stop)
        self.__discover_mode_timer.start()

        self.__module_log = []

        return {'status' : ret['resp']}

    def module_discover_stop(self):
        """ Stop the module discover mode on the master.

        :returns: dict with 'status' ('OK').
        """
        ret = self.__master_communicator.do_command(master_api.module_discover_stop())

        if self.__discover_mode_timer != None:
            self.__discover_mode_timer.cancel()
            self.__discover_mode_timer = None

        self.__module_log = []

        return {'status' : ret['resp']}

    def get_module_log(self):
        """ Get the log messages from the module discovery mode. This returns the current log
        messages and clear the log messages.
        
        :returns: dict with 'log' (list of tuples (log_level, message)).
        """
        (module_log, self.__module_log) = (self.__module_log, [])
        return {'log' : module_log}

    def get_modules(self):
        """ Get a list of all modules attached and registered with the master.

        :returns: dict with 'output' (list of module types: O,R,D) and 'input' \
        (list of input module types: I,T,L).
        """
        mods = self.__master_communicator.do_command(master_api.number_of_io_modules())

        inputs = []
        outputs = []

        for i in range(mods['in']):
            ret = self.__master_communicator.do_command(
                            master_api.read_eeprom(),
                            {'bank' : 2 + i, 'addr' : 0, 'num' : 1})

            inputs.append(ret['data'][0])

        for i in range(mods['out']):
            ret = self.__master_communicator.do_command(
                            master_api.read_eeprom(),
                            {'bank' : 33 + i, 'addr' : 0, 'num' : 1})

            outputs.append(ret['data'][0])

        return {'outputs' : outputs, 'inputs' : inputs}

    def flash_leds(self, type, id):
        """ Flash the leds on the module for an output/input/sensor.

        :type type: byte
        :param type: The module type: output/dimmer (0), input (1), sensor/temperatur (2).
        :type id: bytes
        :param id: The id of the output/input/sensor.
        :returns: dict with 'status' ('OK').
        """
        ret = self.__master_communicator.do_command(master_api.indicate(),
                                                    {'type' : type, 'id' : id})
        return {'status' : ret['resp']}


    ###### Output functions

    def __read_outputs(self):
        """ Read all output information from the MasterApi.

        :returns: a list of dicts with all fields from master_api.read_output.
        """
        ret = self.__master_communicator.do_command(master_api.number_of_io_modules())
        num_outputs = ret['out'] * 8

        outputs = []
        for i in range(0, num_outputs):
            outputs.append(self.__master_communicator.do_command(master_api.read_output(),
                                                                 {'id' : i}))
        return outputs

    def __update_outputs(self, ol_output):
        """ Update the OutputStatus when an OL is received. """
        on_outputs = ol_output['outputs']

        if self.__output_status != None:
            self.__output_status.partial_update(on_outputs)

        if self.__plugin_controller != None:
            self.__plugin_controller.process_output_status(on_outputs)

    def get_output_status(self):
        """ Get a list containing the status of the Outputs.

        :returns: A list is a dicts containing the following keys: id, status, ctimer
        and dimmer.
        """
        if self.__output_status == None:
            self.__output_status = OutputStatus(self.__read_outputs())

        if self.__output_status.should_refresh():
            self.__output_status.full_update(self.__read_outputs())

        outputs = self.__output_status.get_outputs()
        return [{'id':output['id'], 'status':output['status'],
                 'ctimer':output['ctimer'], 'dimmer':output['dimmer']}
                 for output in outputs]

    def set_output(self, id, is_on, dimmer=None, timer=None):
        """ Set the status, dimmer and timer of an output.

        :param id: The id of the output to set
        :type id: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in [150, 450, 900, 1500, 2220, 3120]
        :returns: emtpy dict.
        """
        if not is_on:
            if dimmer != None or timer != None:
                raise ValueError("Cannot set timer and dimmer when setting output to off")
            else:
                self.set_output_status(id, False)
        else:
            if dimmer != None:
                self.set_output_dimmer(id, dimmer)

            self.set_output_status(id, True)

            if timer != None:
                self.set_output_timer(id, timer)

        return dict()

    def set_output_status(self, id, is_on):
        """ Set the status of an output.

        :param id: The id of the output to set
        :type id: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :returns: empty dict.
        """
        if id < 0 or id > 240:
            raise ValueError("id not in [0, 240]: %d" % id)

        if is_on:
            self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_LIGHT_ON, "action_number" : id})
        else:
            self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_LIGHT_OFF, "action_number" : id})

        return dict()

    def set_output_dimmer(self, id, dimmer):
        """ Set the dimmer of an output.

        :param id: The id of the output to set
        :type id: Integer [0, 240]
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :returns: empty dict.
        """
        if id < 0 or id > 240:
            raise ValueError("id not in [0, 240]: %d" % id)

        if dimmer < 0 or dimmer > 100:
            raise ValueError("Dimmer value not in [0, 100]: %d" % dimmer)

        dimmer = int(dimmer) / 10 * 10

        if dimmer == 0:
            dimmer_action = master_api.BA_DIMMER_MIN
        elif dimmer == 100:
            dimmer_action = master_api.BA_DIMMER_MAX
        else:
            dimmer_action = master_api.__dict__['BA_LIGHT_ON_DIMMER_' + str(dimmer)]

        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : dimmer_action, "action_number" : id})

        return dict()

    def set_output_timer(self, id, timer):
        """ Set the timer of an output.

        :param id: The id of the output to set
        :type id: Integer [0, 240]
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in [150, 450, 900, 1500, 2220, 3120]
        :returns: empty dict.
        """
        if id < 0 or id > 240:
            raise ValueError("id not in [0, 240]: %d" % id)

        if timer not in [150, 450, 900, 1500, 2220, 3120]:
            raise ValueError("Timer value not in [150, 450, 900, 1500, 2220, 3120]: %d" % timer)

        timer_action = master_api.__dict__['BA_LIGHT_ON_TIMER_'+str(timer)+'_OVERRULE']

        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : timer_action, "action_number" : id})

        return dict()

    def set_all_lights_off(self):
        """ Turn all lights off.

        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_ALL_LIGHTS_OFF, "action_number" : 0})

        return dict()

    def set_all_lights_floor_off(self, floor):
        """ Turn all lights on a given floor off.

        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_LIGHTS_OFF_FLOOR, "action_number" : floor})

        return dict()

    def set_all_lights_floor_on(self, floor):
        """ Turn all lights on a given floor on.

        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_LIGHTS_ON_FLOOR, "action_number" : floor})

        return dict()

    ###### Input functions

    def __update_inputs(self, api_data):
        """ Update the InputStatus with data from an IL message. """
        tuple = (api_data['input'], api_data['output'])
        self.__input_status.add_data(tuple)
        if self.__plugin_controller != None:
            self.__plugin_controller.process_input_status(tuple)

    def get_last_inputs(self):
        """ Get the 5 last pressed inputs during the last 5 minutes.

        :returns: a list of tuples (input, output).
        """
        return self.__input_status.get_status()

    ###### Thermostat functions

    def __get_all_thermostats(self):
        """ Get basic information about all thermostats.

        :returns: array containing 24 dicts (one for each thermostats) with the following keys: \
        'active', 'sensor_nr', 'output0_nr', 'output1_nr', 'name'.
        """
        thermostats = []
        for thermostat_id in range(0, 24):
            thermostat = self.__master_communicator.do_command(master_api.read_setpoint(),
                                                               {'thermostat' :  thermostat_id})
            info = {}
            info['active'] = (thermostat['sensor_nr'] < 30 or  thermostat['sensor_nr'] == 240) \
                             and thermostat['output0_nr'] < 240
            info['sensor_nr'] = thermostat['sensor_nr']
            info['output0_nr'] = thermostat['output0_nr']
            info['output1_nr'] = thermostat['output1_nr']
            info['name'] = thermostat['name']

            thermostats.append(info)

        return thermostats

    def get_thermostat_status(self):
        """ Get the status of the thermostats.

        :returns: dict with global status information about the thermostats: 'thermostats_on',
        'automatic' and 'setpoint' and a list ('status') with status information for all
        thermostats, each element in the list is a dict with the following keys:
        'id', 'act', 'csetp', 'output0', 'output1', 'outside', 'mode', 'name', 'sensor_nr'.
        """
        if self.__thermostat_status == None:
            self.__thermostat_status = ThermostatStatus(self.__get_all_thermostats(), 1800)
        elif self.__thermostat_status.should_refresh():
            self.__thermostat_status.update(self.__get_all_thermostats())
        cached_thermostats = self.__thermostat_status.get_thermostats()

        thermostat_info = self.__master_communicator.do_command(master_api.thermostat_list())

        mode = thermostat_info['mode']

        thermostats_on = (mode & 128 == 128)
        automatic = (mode & 8 == 8)
        setpoint = 0 if automatic else (mode & 7)

        thermostats = []
        outputs = self.get_output_status()

        for thermostat_id in range(0, 24):
            if cached_thermostats[thermostat_id]['active'] == True:
                thermostat = {'id' : thermostat_id}
                thermostat['act'] = thermostat_info['tmp' + str(thermostat_id)].get_temperature()
                thermostat['csetp'] = thermostat_info['setp' + str(thermostat_id)].get_temperature()
                thermostat['outside'] = thermostat_info['outside'].get_temperature()
                thermostat['mode'] = thermostat_info['mode']

                output0_nr = cached_thermostats[thermostat_id]['output0_nr']
                if output0_nr < len(outputs) and outputs[output0_nr]['status'] == 1:
                    thermostat['output0'] = outputs[output0_nr]['dimmer']
                else:
                    thermostat['output0'] = 0

                output1_nr = cached_thermostats[thermostat_id]['output1_nr']
                if output1_nr < len(outputs) and outputs[output1_nr]['status'] == 1:
                    thermostat['output1'] = outputs[output1_nr]['dimmer']
                else:
                    thermostat['output1'] = 0

                thermostat['name'] = cached_thermostats[thermostat_id]['name']
                thermostat['sensor_nr'] = cached_thermostats[thermostat_id]['sensor_nr']

                thermostats.append(thermostat)

        return {'thermostats_on' : thermostats_on, 'automatic' : automatic,
                'setpoint' : setpoint, 'status' : thermostats}

    def __check_thermostat(self, thermostat):
        """ :raises ValueError if thermostat not in range [0, 24]. """
        if thermostat not in range(0, 25):
            raise ValueError("Thermostat not in [0,24]: %d" % thermostat)

    def set_current_setpoint(self, thermostat, temperature):
        """ Set the current setpoint of a thermostat.

        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :returns: dict with 'thermostat', 'config' and 'temp'
        """
        self.__check_thermostat(thermostat)

        _ = self.__master_communicator.do_command(master_api.write_setpoint(),
            {'thermostat' : thermostat, 'config' : 0, 'temp' : master_api.Svt.temp(temperature)})

        return {'status': 'OK'}

    def set_thermostat_mode(self, thermostat_on, automatic, setpoint):
        """ Set the mode of the thermostats. Thermostats can be on or off, automatic or manual
        and is set to one of the 6 setpoints.

        :param thermostat_on: Whether the thermostats are on
        :type thermostat_on: boolean
        :param automatic: Automatic mode (True) or Manual mode (False)
        :type automatic: boolean
        :param setpoint: The current setpoint
        :type setpoint: Integer [0, 5]

        :returns: dict with 'status'
        """
        def check_resp(ret_dict):
            """ Checks if the response is 'OK', throws a ValueError otherwise. """
            if ret_dict['resp'] != 'OK':
                raise ValueError("Setting thermostat mode did not return OK !")

        if setpoint not in range(0, 6):
            raise ValueError("Setpoint not in [0,5]: " + str(setpoint))

        if automatic:
            check_resp(self.__master_communicator.do_command(master_api.basic_action(),
                    {'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 255}))
        else:
            check_resp(self.__master_communicator.do_command(master_api.basic_action(),
                {'action_type' : master_api.BA_THERMOSTAT_AUTOMATIC, 'action_number' : 0}))

            check_resp(self.__master_communicator.do_command(master_api.basic_action(),
                {'action_type' : master_api.__dict__['BA_ALL_SETPOINT_' + str(setpoint)],
                 'action_number' : 0}))

        return {'status': 'OK'}

    ###### Sensor status

    def get_sensor_temperature_status(self):
        """ Get the current temperature of all sensors.

        :returns: list with 32 temperatures, 1 for each sensor.
        """
        output = []

        list = self.__master_communicator.do_command(master_api.sensor_temperature_list())

        for i in range(32):
            output.append(list['tmp%d' % i].get_temperature())

        return output

    def get_sensor_humidity_status(self):
        """ Get the current humidity of all sensors.

        :returns: list with 32 bytes, 1 for each sensor.
        """
        output = []

        list = self.__master_communicator.do_command(master_api.sensor_humidity_list())

        for i in range(32):
            output.append(list['hum%d' % i])

        return output

    def get_sensor_brightness_status(self):
        """ Get the current brightness of all sensors.

        :returns: list with 32 bytes, 1 for each sensor.
        """
        output = []

        list = self.__master_communicator.do_command(master_api.sensor_brightness_list())

        for i in range(32):
            output.append(list['bri%d' % i])

        return output

    ###### Group actions

    def do_group_action(self, group_action_id):
        """ Execute a group action.

        :param group_action_id: The id of the group action
        :type group_action_id: Integer (0 - 159)
        :returns: empty dict.
        """
        if group_action_id < 0 or group_action_id > 159:
            raise ValueError("group_action_id not in [0, 160]: %d" % group_action_id)

        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_GROUP_ACTION,
                     "action_number" : group_action_id})

        return dict()

    ###### Backup and restore functions

    def get_master_backup(self):
        """ Get a backup of the eeprom of the master.

        :returns: String of bytes (size = 64kb).
        """
        output = ""
        for bank in range(0, 256):
            output += self.__master_communicator.do_command(master_api.eeprom_list(),
                {'bank' : bank})['data']
        return output

    def master_restore(self, data):
        """ Restore a backup of the eeprom of the master.

        :param data: The eeprom backup to restore.
        :type data: string of bytes (size = 64 kb).
        :returns: dict with 'output' key (contains an array with the addresses that were written).
        """
        ret = []
        (num_banks, bank_size, write_size) = (256, 256, 10)

        for bank in range(0, num_banks):
            read = self.__master_communicator.do_command(master_api.eeprom_list(),
                                                         {'bank' : bank})['data']
            for addr in range(0, bank_size, write_size):
                orig = read[addr:addr + write_size]
                new = data[bank * bank_size + addr : bank * bank_size + addr + len(orig)]
                if new != orig:
                    ret.append("B" + str(bank) + "A" + str(addr))

                    self.__master_communicator.do_command(master_api.write_eeprom(),
                        {'bank': bank, 'address': addr, 'data': new})

        self.__master_communicator.do_command(master_api.activate_eeprom(), {'eep' : 0})
        ret.append("Activated eeprom")

        return {'output' : ret}

    def master_reset(self):
        """ Reset the master.

        :returns: emtpy dict.
        """
        self.__master_communicator.do_command(master_api.reset())
        return dict()

    ###### Error functions

    def master_error_list(self):
        """ Get the error list per module (input and output modules). The modules are identified by
        O1, O2, I1, I2, ...

        :returns: dict with 'errors' key, it contains list of tuples (module, nr_errors).
        """
        list = self.__master_communicator.do_command(master_api.error_list())
        return list["errors"]

    def master_last_success(self):
        """ Get the number of seconds since the last successful communication with the master.
        """
        return self.__master_communicator.get_seconds_since_last_success()

    def power_last_success(self):
        """ Get the number of seconds since the last successful communication with the power
        modules.
        """
        return self.__power_communicator.get_seconds_since_last_success()

    def master_clear_error_list(self):
        """ Clear the number of errors.

        :returns: empty dict.
        """
        self.__master_communicator.do_command(master_api.clear_error_list())
        return dict()

    ###### Status led functions

    def set_master_status_leds(self, status):
        """ Set the status of the leds on the master.

        :param status: whether the leds should be on or off.
        :type status: boolean.
        :returns: empty dict.
        """
        on = 1 if status == True else 0
        self.__master_communicator.do_command(master_api.basic_action(),
                    {"action_type" : master_api.BA_STATUS_LEDS, "action_number" : on})
        return dict()

    ###### Pulse counter functions

    def get_pulse_counter_status(self):
        """ Get the pulse counter values.

        :returns: array with the 8 pulse counter values.
        """
        out_dict = self.__master_communicator.do_command(master_api.pulse_list())
        return [out_dict['pv0'], out_dict['pv1'], out_dict['pv2'], out_dict['pv3'],
                out_dict['pv4'], out_dict['pv5'], out_dict['pv6'], out_dict['pv7']]

    ###### Below are the auto generated master configuration functions
    def get_output_configuration(self, id, fields=None):
        """
        Get a specific output_configuration defined by its id.

        :param id: The id of the output_configuration
        :type id: Id
        :param fields: The field of the output_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'module_type' (String[1]), 'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        return self.__eeprom_controller.read(OutputConfiguration, id, fields).to_dict()

    def get_output_configurations(self, fields=None):
        """
        Get all output_configurations.

        :param fields: The field of the output_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'module_type' (String[1]), 'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(OutputConfiguration, fields)]

    def set_output_configuration(self, config):
        """
        Set one output_configuration.

        :param config: The output_configuration to set
        :type config: output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        self.__eeprom_controller.write(OutputConfiguration.from_dict(config))

    def set_output_configurations(self, config):
        """
        Set multiple output_configurations.

        :param config: The list of output_configurations to set
        :type config: list of output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        self.__eeprom_controller.write_batch([OutputConfiguration.from_dict(o) for o in config])

    def get_input_configuration(self, id, fields=None):
        """
        Get a specific input_configuration defined by its id.

        :param id: The id of the input_configuration
        :type id: Id
        :param fields: The field of the input_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'module_type' (String[1]), \
        'name' (String[8])
        """
        return self.__eeprom_controller.read(InputConfiguration, id, fields).to_dict()

    def get_input_configurations(self, fields=None):
        """
        Get all input_configurations.

        :param fields: The field of the input_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'module_type' (String[1]), \
        'name' (String[8])
        """
        return [o.to_dict() for o in self.__eeprom_controller.read_all(InputConfiguration, fields)]

    def set_input_configuration(self, config):
        """
        Set one input_configuration.

        :param config: The input_configuration to set
        :type config: input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'name' (String[8])
        """
        self.__eeprom_controller.write(InputConfiguration.from_dict(config))

    def set_input_configurations(self, config):
        """
        Set multiple input_configurations.

        :param config: The list of input_configurations to set
        :type config: list of input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'name' (String[8])
        """
        self.__eeprom_controller.write_batch([InputConfiguration.from_dict(o) for o in config])

    def get_thermostat_configuration(self, id, fields=None):
        """
        Get a specific thermostat_configuration defined by its id.

        :param id: The id of the thermostat_configuration
        :type id: Id
        :param fields: The field of the thermostat_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: thermostat_configuration dict: contains 'id' (Id), \
        'auto_fri' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_mon' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sat' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sun' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_thu' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_tue' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_wed' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'name' (String[16]), 'output0' (Byte), 'output1' (Byte), 'pid_d' (Byte), 'pid_i' (Byte), \
        'pid_int' (Byte), 'pid_p' (Byte), 'sensor' (Byte), 'setp0' (Temp), 'setp1' (Temp), \
        'setp2' (Temp), 'setp3' (Temp), 'setp4' (Temp), 'setp5' (Temp)
        """
        return self.__eeprom_controller.read(ThermostatConfiguration, id, fields).to_dict()

    def get_thermostat_configurations(self, fields=None):
        """
        Get all thermostat_configurations.

        :param fields: The field of the thermostat_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of thermostat_configuration dict: contains 'id' (Id), \
        'auto_fri' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_mon' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sat' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sun' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_thu' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_tue' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_wed' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'name' (String[16]), 'output0' (Byte), 'output1' (Byte), 'pid_d' (Byte), 'pid_i' (Byte), \
        'pid_int' (Byte), 'pid_p' (Byte), 'sensor' (Byte), 'setp0' (Temp), 'setp1' (Temp), \
        'setp2' (Temp), 'setp3' (Temp), 'setp4' (Temp), 'setp5' (Temp)
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(ThermostatConfiguration, fields)]

    def set_thermostat_configuration(self, config):
        """
        Set one thermostat_configuration.

        :param config: The thermostat_configuration to set
        :type config: thermostat_configuration dict: contains 'id' (Id), \
        'auto_fri' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_mon' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sat' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sun' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_thu' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_tue' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_wed' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'name' (String[16]), 'output0' (Byte), 'output1' (Byte), 'pid_d' (Byte), 'pid_i' (Byte), \
        'pid_int' (Byte), 'pid_p' (Byte), 'sensor' (Byte), 'setp0' (Temp), 'setp1' (Temp), \
        'setp2' (Temp), 'setp3' (Temp), 'setp4' (Temp), 'setp5' (Temp)
        """
        self.__eeprom_controller.write(ThermostatConfiguration.from_dict(config))
        if self.__thermostat_status != None:
            self.__thermostat_status.force_refresh()

    def set_thermostat_configurations(self, config):
        """
        Set multiple thermostat_configurations.

        :param config: The list of thermostat_configurations to set
        :type config: list of thermostat_configuration dict: contains 'id' (Id), \
        'auto_fri' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_mon' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sat' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_sun' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_thu' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_tue' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'auto_wed' ([temp_n(Temp),start_d1(Time),stop_d1(Time),temp_d1(Temp),start_d2(Time),\
        stop_d2(Time),temp_d2(Temp)]), \
        'name' (String[16]), 'output0' (Byte), 'output1' (Byte), 'pid_d' (Byte), 'pid_i' (Byte), \
        'pid_int' (Byte), 'pid_p' (Byte), 'sensor' (Byte), 'setp0' (Temp), 'setp1' (Temp), \
        'setp2' (Temp), 'setp3' (Temp), 'setp4' (Temp), 'setp5' (Temp)
        """
        self.__eeprom_controller.write_batch(
                [ThermostatConfiguration.from_dict(o) for o in config])
        if self.__thermostat_status != None:
            self.__thermostat_status.force_refresh()

    def get_sensor_configuration(self, id, fields=None):
        """
        Get a specific sensor_configuration defined by its id.

        :param id: The id of the sensor_configuration
        :type id: Id
        :param fields: The field of the sensor_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        return self.__eeprom_controller.read(SensorConfiguration, id, fields).to_dict()

    def get_sensor_configurations(self, fields=None):
        """
        Get all sensor_configurations.

        :param fields: The field of the sensor_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(SensorConfiguration, fields)]

    def set_sensor_configuration(self, config):
        """
        Set one sensor_configuration.

        :param config: The sensor_configuration to set
        :type config: sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.__eeprom_controller.write(SensorConfiguration.from_dict(config))

    def set_sensor_configurations(self, config):
        """
        Set multiple sensor_configurations.

        :param config: The list of sensor_configurations to set
        :type config: list of sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.__eeprom_controller.write_batch([SensorConfiguration.from_dict(o) for o in config])

    def get_pump_group_configuration(self, id, fields=None):
        """
        Get a specific pump_group_configuration defined by its id.

        :param id: The id of the pump_group_configuration
        :type id: Id
        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32])
        """
        return self.__eeprom_controller.read(PumpGroupConfiguration, id, fields).to_dict()

    def get_pump_group_configurations(self, fields=None):
        """
        Get all pump_group_configurations.

        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32])
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(PumpGroupConfiguration, fields)]

    def set_pump_group_configuration(self, config):
        """
        Set one pump_group_configuration.

        :param config: The pump_group_configuration to set
        :type config: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32])
        """
        self.__eeprom_controller.write(PumpGroupConfiguration.from_dict(config))

    def set_pump_group_configurations(self, config):
        """
        Set multiple pump_group_configurations.

        :param config: The list of pump_group_configurations to set
        :type config: list of pump_group_configuration dict: contains 'id' (Id), \
        'outputs' (CSV[32])
        """
        self.__eeprom_controller.write_batch([PumpGroupConfiguration.from_dict(o) for o in config])

    def get_group_action_configuration(self, id, fields=None):
        """
        Get a specific group_action_configuration defined by its id.

        :param id: The id of the group_action_configuration
        :type id: Id
        :param fields: The field of the group_action_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: group_action_configuration dict: contains 'id' (Id), 'actions' (Actions[16]), \
        'name' (String[16])
        """
        return self.__eeprom_controller.read(GroupActionConfiguration, id, fields).to_dict()

    def get_group_action_configurations(self, fields=None):
        """
        Get all group_action_configurations.

        :param fields: The field of the group_action_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(GroupActionConfiguration, fields)]

    def set_group_action_configuration(self, config):
        """
        Set one group_action_configuration.

        :param config: The group_action_configuration to set
        :type config: group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.__eeprom_controller.write(GroupActionConfiguration.from_dict(config))

    def set_group_action_configurations(self, config):
        """
        Set multiple group_action_configurations.

        :param config: The list of group_action_configurations to set
        :type config: list of group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.__eeprom_controller.write_batch(
                [GroupActionConfiguration.from_dict(o) for o in config])

    def get_scheduled_action_configuration(self, id, fields=None):
        """
        Get a specific scheduled_action_configuration defined by its id.

        :param id: The id of the scheduled_action_configuration
        :type id: Id
        :param fields: The field of the scheduled_action_configuration to get. \
        (None gets all fields)
        :type fields: List of strings
        :returns: scheduled_action_configuration dict: contains 'id' (Id), 'action' (Actions[1]), \
        'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        return self.__eeprom_controller.read(ScheduledActionConfiguration, id, fields).to_dict()

    def get_scheduled_action_configurations(self, fields=None):
        """
        Get all scheduled_action_configurations.

        :param fields: The field of the scheduled_action_configuration to get. \
        (None gets all fields)
        :type fields: List of strings
        :returns: list of scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(ScheduledActionConfiguration, fields)]

    def set_scheduled_action_configuration(self, config):
        """
        Set one scheduled_action_configuration.

        :param config: The scheduled_action_configuration to set
        :type config: scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.__eeprom_controller.write(ScheduledActionConfiguration.from_dict(config))

    def set_scheduled_action_configurations(self, config):
        """
        Set multiple scheduled_action_configurations.

        :param config: The list of scheduled_action_configurations to set
        :type config: list of scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.__eeprom_controller.write_batch(
                [ScheduledActionConfiguration.from_dict(o) for o in config])

    def get_pulse_counter_configuration(self, id, fields=None):
        """
        Get a specific pulse_counter_configuration defined by its id.

        :param id: The id of the pulse_counter_configuration
        :type id: Id
        :param fields: The field of the pulse_counter_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: pulse_counter_configuration dict: contains 'id' (Id), 'input' (Byte), \
        'name' (String[16])
        """
        return self.__eeprom_controller.read(PulseCounterConfiguration, id, fields).to_dict()

    def get_pulse_counter_configurations(self, fields=None):
        """
        Get all pulse_counter_configurations.

        :param fields: The field of the pulse_counter_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: list of pulse_counter_configuration dict: contains 'id' (Id), 'input' (Byte), \
        'name' (String[16])
        """
        return [o.to_dict()
                for o in self.__eeprom_controller.read_all(PulseCounterConfiguration, fields)]

    def set_pulse_counter_configuration(self, config):
        """
        Set one pulse_counter_configuration.

        :param config: The pulse_counter_configuration to set
        :type config: pulse_counter_configuration dict: contains 'id' (Id), 'input' (Byte), \
        'name' (String[16])
        """
        self.__eeprom_controller.write(PulseCounterConfiguration.from_dict(config))

    def set_pulse_counter_configurations(self, config):
        """
        Set multiple pulse_counter_configurations.

        :param config: The list of pulse_counter_configurations to set
        :type config: list of pulse_counter_configuration dict: contains 'id' (Id), \
        'input' (Byte), 'name' (String[16])
        """
        self.__eeprom_controller.write_batch(
                [PulseCounterConfiguration.from_dict(o) for o in config])

    def get_startup_action_configuration(self, fields=None):
        """
        Get the startup_action_configuration.

        :param fields: The field of the startup_action_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: startup_action_configuration dict: contains 'actions' (Actions[100])
        """
        return self.__eeprom_controller.read(StartupActionConfiguration, fields).to_dict()

    def set_startup_action_configuration(self, config):
        """
        Set the startup_action_configuration.

        :param config: The startup_action_configuration to set
        :type config: startup_action_configuration dict: contains 'actions' (Actions[100])
        """
        self.__eeprom_controller.write(StartupActionConfiguration.from_dict(config))

    def get_dimmer_configuration(self, fields=None):
        """
        Get the dimmer_configuration.

        :param fields: The field of the dimmer_configuration to get. (None gets all fields)
        :type fields: List of strings
        :returns: dimmer_configuration dict: contains 'dim_memory' (Byte), 'dim_step' (Byte), \
        'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        """
        return self.__eeprom_controller.read(DimmerConfiguration, fields).to_dict()

    def set_dimmer_configuration(self, config):
        """
        Set the dimmer_configuration.

        :param config: The dimmer_configuration to set
        :type config: dimmer_configuration dict: contains 'dim_memory' (Byte), 'dim_step' (Byte), \
        'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        """
        self.__eeprom_controller.write(DimmerConfiguration.from_dict(config))

    def get_global_thermostat_configuration(self, fields=None):
        """
        Get the global_thermostat_configuration.

        :param fields: The field of the global_thermostat_configuration to get. \
        (None gets all fields)
        :type fields: List of strings
        :returns: global_thermostat_configuration dict: contains 'outside_sensor' (Byte), \
        'pump_delay' (Byte), 'threshold_temp' (Temp)
        """
        return self.__eeprom_controller.read(GlobalThermostatConfiguration, fields).to_dict()

    def set_global_thermostat_configuration(self, config):
        """
        Set the global_thermostat_configuration.

        :param config: The global_thermostat_configuration to set
        :type config: global_thermostat_configuration dict: contains 'outside_sensor' (Byte), \
        'pump_delay' (Byte), 'threshold_temp' (Temp)
        """
        self.__eeprom_controller.write(GlobalThermostatConfiguration.from_dict(config))



    ###### End of auto generated functions

    ###### Power functions

    def get_power_modules(self):
        """ Get information on the power modules.

        :returns: List of dictionaries with the following keys: 'id', 'name', 'address', \
        'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', 'input7', \
        'sensor0', 'sensor1', 'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', \
        'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        modules = self.__power_controller.get_power_modules().values()
        def translate_address(module):
            """ Translate the address from an integer to the external address format (eg. E1). """
            module['address'] = "E" + str(module['address'])
            return module
        return [translate_address(module) for module in modules]

    def set_power_modules(self, modules):
        """ Set information for the power modules.

        :param modules: list of dicts with keys: 'id', 'name', 'input0', 'input1', \
        'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', \
        'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', \
        'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        :returns: empty dict.
        """
        for module in modules:
            self.__power_controller.update_power_module(module)
            addr = self.__power_controller.get_address(module['id'])

            self.__power_communicator.do_command(addr, power_api.set_sensor_types(),
                    module["sensor0"], module["sensor1"], module["sensor2"], module["sensor3"],
                    module["sensor4"], module["sensor5"], module["sensor6"], module["sensor7"])

        return dict()

    def get_realtime_power(self):
        """ Get the realtime power measurement values.

        :returns: dict with the module id as key and the following array as value: \
        [voltage, frequency, current, power].
        """
        output = dict()

        modules = self.__power_controller.get_power_modules()
        for id in sorted(modules.keys()):
            try:
                addr = modules[id]['address']

                volt = self.__power_communicator.do_command(addr, power_api.get_voltage())[0]
                freq = self.__power_communicator.do_command(addr, power_api.get_frequency())[0]
                current = self.__power_communicator.do_command(addr, power_api.get_current())
                power = self.__power_communicator.do_command(addr, power_api.get_power())

                out = []
                for i in range(0, 8):
                    out.append([convert_nan(volt), convert_nan(freq), convert_nan(current[i]),
                                convert_nan(power[i])])

                output[str(id)] = out
            except Exception as exception:
                LOGGER.exception("Got Exception for power module %s: %s", id, exception)

        return output

    def get_total_energy(self):
        """ Get the total energy (kWh) consumed by the power modules.

        :returns: dict with the module id as key and the following array as value: [day, night].
        """
        output = dict()

        modules = self.__power_controller.get_power_modules()
        for id in sorted(modules.keys()):
            try:
                addr = modules[id]['address']

                day = self.__power_communicator.do_command(addr, power_api.get_day_energy())
                night = self.__power_communicator.do_command(addr, power_api.get_night_energy())

                out = []
                for i in range(0, 8):
                    out.append([convert_nan(day[i]), convert_nan(night[i])])

                output[str(id)] = out
            except Exception:
                LOGGER.error("Got Exception for power module %s", id)

        return output

    def start_power_address_mode(self):
        """ Start the address mode on the power modules.

        :returns: empty dict.
        """
        self.__power_communicator.start_address_mode()
        return dict()

    def stop_power_address_mode(self):
        """ Stop the address mode on the power modules.

        :returns: empty dict
        """
        self.__power_communicator.stop_address_mode()
        return dict()

    def in_power_address_mode(self):
        """ Check if the power modules are in address mode

        :returns: dict with key 'address_mode' and value True or False.
        """
        return {'address_mode' : self.__power_communicator.in_address_mode()}

    def set_power_voltage(self, module_id, voltage):
        """ Set the voltage for a given module.

        :param module_id: The id of the power module.
        :param voltage: The voltage to set for the power module.
        :returns: empty dict
        """
        addr = self.__power_controller.get_address(module_id)
        self.__power_communicator.do_command(addr, power_api.set_voltage(), voltage)
        return dict()
