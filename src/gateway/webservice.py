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

""" Includes the WebService class """
import logging
LOGGER = logging.getLogger("openmotics")

import threading
import random
import ConfigParser
import subprocess
import os
from types import MethodType
import traceback
import inspect
import time
import requests

from gateway.scheduling import SchedulingController

try:
    import json
except ImportError:
    import simplejson as json

class FloatWrapper(float):
    """ Wrapper for float value that limits the number of digits when printed. """

    def __repr__(self):
        return '%.2f' % self

def limit_floats(struct):
    """ Usage: json.dumps(limit_floats(struct)). This limits the number of digits in the json
    string.
    """
    if isinstance(struct, (list, tuple)):
        return [limit_floats(element) for element in struct]
    elif isinstance(struct, dict):
        return dict((key, limit_floats(value)) for key, value in struct.items())
    elif isinstance(struct, float):
        return FloatWrapper(struct)
    else:
        return struct

def boolean(instance):
    """ Convert object (bool, int, float, str) to bool (True of False). """
    if type(instance) == bool:
        return instance
    elif type(instance) == int:
        return instance != 0
    elif type(instance) == float:
        return instance != 0.0
    elif type(instance) == str or type(instance) == unicode:
        return instance.lower() == 'true'

import cherrypy
from cherrypy.lib.static import serve_file

import constants
from master.master_communicator import InMaintenanceModeException

class GatewayApiWrapper(object):
    """ Wraps the GatewayApi, catches the InMaintenanceModeException and converts
    the exception in a HttpError(503).
    """

    def __init__(self, gateway_api):
        self.__gateway_api = gateway_api

    def __getattr__(self, name):
        if hasattr(self.__gateway_api, name):
            return lambda *args, **kwargs: \
                    self._wrap(getattr(self.__gateway_api, name), args, kwargs)
        else:
            raise AttributeError(name)

    def _wrap(self, func, args, kwargs):
        """ Wrap a function, convert the InMaintenanceModeException to a HttpError(503). """
        try:
            if type(func) == MethodType:
                result = func(*args, **kwargs) #pylint: disable=W0142
            else:
                result = func(self.__gateway_api, *args, **kwargs) #pylint: disable=W0142
            return result
        except InMaintenanceModeException:
            raise cherrypy.HTTPError(503, "In maintenance mode")


def timestampFilter():
    """ If the request parameters contain a "fe_time" variable, remove it from the parameters.
    This parameter is used by the gateway frontend to bypass caching by certain browsers.
    """
    if "fe_time" in cherrypy.request.params:
        del cherrypy.request.params["fe_time"]

cherrypy.tools.timestampFilter = cherrypy.Tool('before_handler', timestampFilter)


class DummyToken(object):
    """ The DummyToken is used for internal calls from the plugins to the webinterface, so
    that the plugin does not required a real token. """
    pass


class WebInterface(object):
    """ This class defines the web interface served by cherrypy. """

    def __init__(self, user_controller, gateway_api, scheduling_filename, maintenance_service,
                 authorized_check):
        """ Constructor for the WebInterface.

        :param user_controller: used to create and authenticate users.
        :type user_controller: instance of :class`UserController`.
        :param gateway_api: used to communicate with the master.
        :type gateway_api: instance of :class`GatewayApi`.
        :param scheduling_filename: the filename of the scheduling controller database.
        :type scheduling_filename: string.
        :param maintenance_service: used when opening maintenance mode.
        :type maintenance_server: instance of :class`MaintenanceService`.
        :param authorized_check: check if the gateway is in authorized mode.
        :type authorized_check: function (called without arguments).
        """
        self.__user_controller = user_controller
        self.__gateway_api = GatewayApiWrapper(gateway_api)

        self.__scheduling_controller = SchedulingController(scheduling_filename,
                                                            self.__exec_scheduled_action)
        self.__scheduling_controller.start()

        self.__maintenance_service = maintenance_service
        self.__authorized_check = authorized_check

        self.__plugin_controller = None
        self.dummy_token = DummyToken()

    def set_plugin_controller(self, plugin_controller):
        """ Set the plugin controller. """
        self.__plugin_controller = plugin_controller

    def check_token(self, token):
        """ Check if the token is valid, raises HTTPError(401) if invalid. """
        if cherrypy.request.remote.ip == '127.0.0.1' or token is self.dummy_token:
            # Don't check tokens for localhost
            return

        if token is None or token == "None":
            # Get the token from the session if no token is provided.
            token = cherrypy.session.get("token", None)

        if not self.__user_controller.check_token(token):
            raise cherrypy.HTTPError(401, "Unauthorized")

    def __error(self, msg):
        """ Returns a dict with 'success' = False and a 'msg' in json format. """
        return json.dumps({"success": False, "msg": msg})

    def __success(self, **kwargs):
        """ Returns a dict with 'success' = True and the keys and values in **kwargs. """
        return json.dumps(limit_floats(dict({"success" : True}.items() + kwargs.items())))

    @cherrypy.expose
    def index(self):
        """ Index page of the web service.

        :returns: msg (String)
        """
        if cherrypy.session.get("token", None) is None:
            return serve_file('/opt/openmotics/static/login.html', content_type='text/html')
        else:
            return serve_file('/opt/openmotics/static/index.html', content_type='text/html')

    @cherrypy.expose
    def login(self, username, password):
        """ Login to the web service, returns a token if successful, returns HTTP status code 401
        otherwise.

        :type username: String
        :param username: Name of the user.
        :type password: String
        :param password: Password of the user.
        :returns: 'token' : String
        """
        token = self.__user_controller.login(username, password)
        if token == None:
            raise cherrypy.HTTPError(401, "Unauthorized")
        else:
            # Store the token in the session
            cherrypy.session.regenerate()
            cherrypy.session['token'] = token
            return self.__success(token=token)

    @cherrypy.expose
    def logout(self, token):
        """ Logout from the web service.

        :returns: 'status': 'OK'
        """
        self.__user_controller.logout(token)
        cherrypy.session.clear()
        return self.__success(status='OK')

    @cherrypy.expose
    def create_user(self, username, password):
        """ Create a new user using a username and a password. Only possible in authorized mode.

        :type username: String
        :param username: Name of the user.
        :type password: String
        :param password: Password of the user.
        """
        if self.__authorized_check():
            self.__user_controller.create_user(username, password, 'admin', True)
            return self.__success()
        else:
            raise cherrypy.HTTPError(401, "Unauthorized")

    @cherrypy.expose
    def get_usernames(self):
        """ Get the names of the users on the gateway. Only possible in authorized mode.

        :returns: 'usernames': list of usernames (String).
        """
        if self.__authorized_check():
            return self.__success(usernames=self.__user_controller.get_usernames())
        else:
            raise cherrypy.HTTPError(401, "Unauthorized")

    @cherrypy.expose
    def remove_user(self, username):
        """ Remove a user. Only possible in authorized mode.

        :type username: String
        :param username: Name of the user to remove.
        """
        if self.__authorized_check():
            self.__user_controller.remove_user(username)
            return self.__success()
        else:
            raise cherrypy.HTTPError(401, "Unauthorized")

    @cherrypy.expose
    def open_maintenance(self, token):
        """ Open maintenance mode, return the port of the maintenance socket.

        :returns: 'port': Port on which the maintenance ssl socket is listening \
        (Integer between 6000 and 7000).
        """
        self.check_token(token)

        port = random.randint(6000, 7000)
        self.__maintenance_service.start_in_thread(port)
        return self.__success(port=port)

    @cherrypy.expose
    def reset_master(self, token):
        """ Perform a cold reset on the master.

        :returns: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.reset_master)

    @cherrypy.expose
    def module_discover_start(self, token):
        """ Start the module discover mode on the master.

        :returns: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.module_discover_start)

    @cherrypy.expose
    def module_discover_stop(self, token):
        """ Stop the module discover mode on the master.

        :returns: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.module_discover_stop)

    @cherrypy.expose
    def get_module_log(self, token):
        """ Get the log messages from the module discovery mode. This returns the current log
        messages and clear the log messages.

        :returns: 'log': list of tuples (log_level, message).
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.get_module_log)

    @cherrypy.expose
    def get_modules(self, token):
        """ Get a list of all modules attached and registered with the master.

        :returns: 'output': list of module types (O,R,D) and 'input': list of input module \
        types (I,T,L).
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.get_modules)

    @cherrypy.expose
    def flash_leds(self, token, type, id):
        """ Flash the leds on the module for an output/input/sensor.

        :type type: Integer
        :param type: The module type: output/dimmer (0), input (1), sensor/temperatur (2).
        :type id: Integer
        :param id: The id of the output/input/sensor.
        :returns: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.flash_leds(int(type), int(id)))

    @cherrypy.expose
    def get_status(self, token):
        """ Get the status of the master.

        :returns: 'time': hour and minutes (HH:MM), 'date': day, month, year (DD:MM:YYYY), \
        'mode': Integer, 'version': a.b.c and 'hw_version': hardware version (Integer).
        """
        self.check_token(token)
        return self.__success(**self.__gateway_api.get_status())

    @cherrypy.expose
    def get_output_status(self, token):
        """ Get the status of the outputs.

        :returns: 'status': list of dictionaries with the following keys: id,\
        status, dimmer and ctimer.
        """
        self.check_token(token)
        return self.__success(status=self.__gateway_api.get_output_status())

    @cherrypy.expose
    def set_output(self, token, id, is_on, dimmer=None, timer=None):
        """ Set the status, dimmer and timer of an output.

        :param id: The id of the output to set
        :type id: Integer [0, 240]
        :param is_on: Whether the output should be on
        :type is_on: Boolean
        :param dimmer: The dimmer value to set, None if unchanged
        :type dimmer: Integer [0, 100] or None
        :param timer: The timer value to set, None if unchanged
        :type timer: Integer in (150, 450, 900, 1500, 2220, 3120)
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_output(
                                        int(id), is_on.lower() == "true",
                                        int(dimmer) if dimmer is not None else None,
                                        int(timer) if timer is not None else None))

    @cherrypy.expose
    def set_all_lights_off(self, token):
        """ Turn all lights off.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.set_all_lights_off)

    @cherrypy.expose
    def set_all_lights_floor_off(self, token, floor):
        """ Turn all lights on a given floor off.

        :param floor: The id of the floor
        :type floor: Byte
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_all_lights_floor_off(int(floor)))

    @cherrypy.expose
    def set_all_lights_floor_on(self, token, floor):
        """ Turn all lights on a given floor on.

        :param floor: The id of the floor
        :type floor: Byte
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_all_lights_floor_on(int(floor)))

    @cherrypy.expose
    def get_last_inputs(self, token):
        """ Get the 5 last pressed inputs during the last 5 minutes.

        :returns: 'inputs': list of tuples (input, output).
        """
        self.check_token(token)
        return self.__success(inputs=self.__gateway_api.get_last_inputs())

    @cherrypy.expose
    def get_thermostat_status(self, token):
        """ Get the status of the thermostats.

        :returns: global status information about the thermostats: 'thermostats_on', \
        'automatic' and 'setpoint' and 'status': a list with status information for all \
        thermostats, each element in the list is a dict with the following keys: \
        'id', 'act', 'csetp', 'output0', 'output1', 'outside', 'mode'.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.get_thermostat_status)

    @cherrypy.expose
    def set_current_setpoint(self, token, thermostat, temperature):
        """ Set the current setpoint of a thermostat.

        :param thermostat: The id of the thermostat to set
        :type thermostat: Integer [0, 24]
        :param temperature: The temperature to set in degrees Celcius
        :type temperature: float
        :return: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_current_setpoint(
                                            int(thermostat), float(temperature)))

    @cherrypy.expose
    def set_thermostat_mode(self, token, thermostat_on, automatic, setpoint):
        """ Set the mode of the thermostats. Thermostats can be on or off, automatic or manual
        and is set to one of the 6 setpoints.

        :param thermostat_on: Whether the thermostats are on
        :type thermostat_on: Boolean
        :param automatic: Automatic mode (True) or Manual mode (False)
        :type automatic: Boolean
        :param setpoint: The current setpoint
        :type setpoint: Integer [0, 5]

        :return: 'status': 'OK'.
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_thermostat_mode(
                       boolean(thermostat_on), boolean(automatic), int(setpoint)))

    @cherrypy.expose
    def get_sensor_temperature_status(self, token):
        """ Get the current temperature of all sensors.

        :returns: 'status': list of 32 temperatures, 1 for each sensor.
        """
        self.check_token(token)
        return self.__success(status=self.__gateway_api.get_sensor_temperature_status())

    @cherrypy.expose
    def get_sensor_humidity_status(self, token):
        """ Get the current humidity of all sensors.

        :returns: 'status': List of 32 bytes, 1 for each sensor.
        """
        self.check_token(token)
        return self.__success(status=self.__gateway_api.get_sensor_humidity_status())

    @cherrypy.expose
    def get_sensor_brightness_status(self, token):
        """ Get the current brightness of all sensors.

        :returns: 'status': List of 32 bytes, 1 for each sensor.
        """
        self.check_token(token)
        return self.__success(status=self.__gateway_api.get_sensor_brightness_status())

    @cherrypy.expose
    def do_group_action(self, token, group_action_id):
        """ Execute a group action.

        :param group_action_id: The id of the group action
        :type group_action_id: Integer [0, 159]
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.do_group_action(int(group_action_id)))

    @cherrypy.expose
    def set_master_status_leds(self, token, status):
        """ Set the status of the leds on the master.

        :param status: whether the leds should be on (true) or off (false).
        :type status: Boolean
        """
        self.check_token(token)
        return self.__wrap(
                    lambda: self.__gateway_api.set_master_status_leds(status.lower() == "true"))

    @cherrypy.expose
    def get_master_backup(self, token):
        """ Get a backup of the eeprom of the master.

        :returns: This function does not return a dict, unlike all other API functions: it \
        returns a string of bytes (size = 64kb).
        """
        self.check_token(token)
        cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
        return self.__gateway_api.get_master_backup()

    @cherrypy.expose
    def master_restore(self, token, data):
        """ Restore a backup of the eeprom of the master.

        :param data: The eeprom backup to restore.
        :type data: multipart/form-data encoded bytes (size = 64 kb).
        :returns: 'output': array with the addresses that were written.
        """
        self.check_token(token)
        data = data.file.read()
        return self.__wrap(lambda: self.__gateway_api.master_restore(data))

    @cherrypy.expose
    def get_errors(self, token):
        """ Get the number of seconds since the last successul communication with the master and
        power modules (master_last_success, power_last_success) and the error list per module
        (input and output modules). The modules are identified by O1, O2, I1, I2, ...

        :returns: 'errors': list of tuples (module, nr_errors), 'master_last_success': UNIX \
        timestamp of the last succesful master communication and 'power_last_success': UNIX \
        timestamp of the last successful power communication.
        """
        self.check_token(token)
        try:
            errors = self.__gateway_api.master_error_list()
        except Exception:
            # In case of communications problems with the master.
            errors = []

        master_last = self.__gateway_api.master_last_success()
        power_last = self.__gateway_api.power_last_success()

        return self.__success(errors=errors, master_last_success=master_last,
                              power_last_success=power_last)

    @cherrypy.expose
    def master_clear_error_list(self, token):
        """ Clear the number of errors.
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.master_clear_error_list)

    ###### Below are the auto generated master configuration api functions

    @cherrypy.expose
    def get_output_configuration(self, token, id, fields=None):
        """
        Get a specific output_configuration defined by its id.

        :param id: The id of the output_configuration
        :type id: Id
        :param fields: The field of the output_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'module_type' (String[1]), 'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_output_configuration(int(id), fields))

    @cherrypy.expose
    def get_output_configurations(self, token, fields=None):
        """
        Get all output_configurations.

        :param fields: The field of the output_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of output_configuration dict: contains 'id' (Id), \
        'floor' (Byte), 'module_type' (String[1]), 'name' (String[16]), 'timer' (Word), \
        'type' (Byte)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_output_configurations(fields))

    @cherrypy.expose
    def set_output_configuration(self, token, config):
        """
        Set one output_configuration.

        :param config: The output_configuration to set
        :type config: output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        self.check_token(token)
        self.__gateway_api.set_output_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_output_configurations(self, token, config):
        """
        Set multiple output_configurations.

        :param config: The list of output_configurations to set
        :type config: list of output_configuration dict: contains 'id' (Id), 'floor' (Byte), \
        'name' (String[16]), 'timer' (Word), 'type' (Byte)
        """
        self.check_token(token)
        self.__gateway_api.set_output_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_input_configuration(self, token, id, fields=None):
        """
        Get a specific input_configuration defined by its id.

        :param id: The id of the input_configuration
        :type id: Id
        :param fields: The field of the input_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'module_type' (String[1]), \
        'name' (String[8])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_input_configuration(int(id), fields))

    @cherrypy.expose
    def get_input_configurations(self, token, fields=None):
        """
        Get all input_configurations.

        :param fields: The field of the input_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of input_configuration dict: contains 'id' (Id), \
        'action' (Byte), 'basic_actions' (Actions[15]), 'invert' (Byte), \
        'module_type' (String[1]), 'name' (String[8])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_input_configurations(fields))

    @cherrypy.expose
    def set_input_configuration(self, token, config):
        """
        Set one input_configuration.

        :param config: The input_configuration to set
        :type config: input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'name' (String[8])
        """
        self.check_token(token)
        self.__gateway_api.set_input_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_input_configurations(self, token, config):
        """
        Set multiple input_configurations.

        :param config: The list of input_configurations to set
        :type config: list of input_configuration dict: contains 'id' (Id), 'action' (Byte), \
        'basic_actions' (Actions[15]), 'invert' (Byte), 'name' (String[8])
        """
        self.check_token(token)
        self.__gateway_api.set_input_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_thermostat_configuration(self, token, id, fields=None):
        """
        Get a specific thermostat_configuration defined by its id.

        :param id: The id of the thermostat_configuration
        :type id: Id
        :param fields: The field of the thermostat_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': thermostat_configuration dict: contains 'id' (Id), \
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
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_thermostat_configuration(int(id), fields))

    @cherrypy.expose
    def get_thermostat_configurations(self, token, fields=None):
        """
        Get all thermostat_configurations.

        :param fields: The field of the thermostat_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of thermostat_configuration dict: contains 'id' (Id), \
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
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_thermostat_configurations(fields))

    @cherrypy.expose
    def set_thermostat_configuration(self, token, config):
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
        self.check_token(token)
        self.__gateway_api.set_thermostat_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_thermostat_configurations(self, token, config):
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
        self.check_token(token)
        self.__gateway_api.set_thermostat_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_sensor_configuration(self, token, id, fields=None):
        """
        Get a specific sensor_configuration defined by its id.

        :param id: The id of the sensor_configuration
        :type id: Id
        :param fields: The field of the sensor_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_sensor_configuration(int(id), fields))

    @cherrypy.expose
    def get_sensor_configurations(self, token, fields=None):
        """
        Get all sensor_configurations.

        :param fields: The field of the sensor_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of sensor_configuration dict: contains 'id' (Id), \
        'name' (String[16]), 'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_sensor_configurations(fields))

    @cherrypy.expose
    def set_sensor_configuration(self, token, config):
        """
        Set one sensor_configuration.

        :param config: The sensor_configuration to set
        :type config: sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.check_token(token)
        self.__gateway_api.set_sensor_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_sensor_configurations(self, token, config):
        """
        Set multiple sensor_configurations.

        :param config: The list of sensor_configurations to set
        :type config: list of sensor_configuration dict: contains 'id' (Id), 'name' (String[16]), \
        'offset' (SignedTemp(-7.5 to 7.5 degrees))
        """
        self.check_token(token)
        self.__gateway_api.set_sensor_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_pump_group_configuration(self, token, id, fields=None):
        """
        Get a specific pump_group_configuration defined by its id.

        :param id: The id of the pump_group_configuration
        :type id: Id
        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_pump_group_configuration(int(id), fields))

    @cherrypy.expose
    def get_pump_group_configurations(self, token, fields=None):
        """
        Get all pump_group_configurations.

        :param fields: The field of the pump_group_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of pump_group_configuration dict: contains 'id' (Id), \
        'outputs' (CSV[32])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_pump_group_configurations(fields))

    @cherrypy.expose
    def set_pump_group_configuration(self, token, config):
        """
        Set one pump_group_configuration.

        :param config: The pump_group_configuration to set
        :type config: pump_group_configuration dict: contains 'id' (Id), 'outputs' (CSV[32])
        """
        self.check_token(token)
        self.__gateway_api.set_pump_group_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_pump_group_configurations(self, token, config):
        """
        Set multiple pump_group_configurations.

        :param config: The list of pump_group_configurations to set
        :type config: list of pump_group_configuration dict: contains 'id' (Id), \
        'outputs' (CSV[32])
        """
        self.check_token(token)
        self.__gateway_api.set_pump_group_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_group_action_configuration(self, token, id, fields=None):
        """
        Get a specific group_action_configuration defined by its id.

        :param id: The id of the group_action_configuration
        :type id: Id
        :param fields: The field of the group_action_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_group_action_configuration(int(id), fields))

    @cherrypy.expose
    def get_group_action_configurations(self, token, fields=None):
        """
        Get all group_action_configurations.

        :param fields: The field of the group_action_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_group_action_configurations(fields))

    @cherrypy.expose
    def set_group_action_configuration(self, token, config):
        """
        Set one group_action_configuration.

        :param config: The group_action_configuration to set
        :type config: group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.check_token(token)
        self.__gateway_api.set_group_action_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_group_action_configurations(self, token, config):
        """
        Set multiple group_action_configurations.

        :param config: The list of group_action_configurations to set
        :type config: list of group_action_configuration dict: contains 'id' (Id), \
        'actions' (Actions[16]), 'name' (String[16])
        """
        self.check_token(token)
        self.__gateway_api.set_group_action_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_scheduled_action_configuration(self, token, id, fields=None):
        """
        Get a specific scheduled_action_configuration defined by its id.

        :param id: The id of the scheduled_action_configuration
        :type id: Id
        :param fields: The field of the scheduled_action_configuration to get. \
        (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_scheduled_action_configuration(int(id), fields))

    @cherrypy.expose
    def get_scheduled_action_configurations(self, token, fields=None):
        """
        Get all scheduled_action_configurations.

        :param fields: The field of the scheduled_action_configuration to get. \
        (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                    config=self.__gateway_api.get_scheduled_action_configurations(fields))

    @cherrypy.expose
    def set_scheduled_action_configuration(self, token, config):
        """
        Set one scheduled_action_configuration.

        :param config: The scheduled_action_configuration to set
        :type config: scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.check_token(token)
        self.__gateway_api.set_scheduled_action_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_scheduled_action_configurations(self, token, config):
        """
        Set multiple scheduled_action_configurations.

        :param config: The list of scheduled_action_configurations to set
        :type config: list of scheduled_action_configuration dict: contains 'id' (Id), \
        'action' (Actions[1]), 'day' (Byte), 'hour' (Byte), 'minute' (Byte)
        """
        self.check_token(token)
        self.__gateway_api.set_scheduled_action_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_pulse_counter_configuration(self, token, id, fields=None):
        """
        Get a specific pulse_counter_configuration defined by its id.

        :param id: The id of the pulse_counter_configuration
        :type id: Id
        :param fields: The field of the pulse_counter_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': pulse_counter_configuration dict: contains 'id' (Id), 'input' (Byte), \
        'name' (String[16])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_pulse_counter_configuration(int(id), fields))

    @cherrypy.expose
    def get_pulse_counter_configurations(self, token, fields=None):
        """
        Get all pulse_counter_configurations.

        :param fields: The field of the pulse_counter_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': list of pulse_counter_configuration dict: contains 'id' (Id), \
        'input' (Byte), 'name' (String[16])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_pulse_counter_configurations(fields))

    @cherrypy.expose
    def set_pulse_counter_configuration(self, token, config):
        """
        Set one pulse_counter_configuration.

        :param config: The pulse_counter_configuration to set
        :type config: pulse_counter_configuration dict: contains 'id' (Id), 'input' (Byte), \
        'name' (String[16])
        """
        self.check_token(token)
        self.__gateway_api.set_pulse_counter_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def set_pulse_counter_configurations(self, token, config):
        """
        Set multiple pulse_counter_configurations.

        :param config: The list of pulse_counter_configurations to set
        :type config: list of pulse_counter_configuration dict: contains 'id' (Id), \
        'input' (Byte), 'name' (String[16])
        """
        self.check_token(token)
        self.__gateway_api.set_pulse_counter_configurations(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_startup_action_configuration(self, token, fields=None):
        """
        Get the startup_action_configuration.

        :param fields: The field of the startup_action_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': startup_action_configuration dict: contains 'actions' (Actions[100])
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_startup_action_configuration(fields))

    @cherrypy.expose
    def set_startup_action_configuration(self, token, config):
        """
        Set the startup_action_configuration.

        :param config: The startup_action_configuration to set
        :type config: startup_action_configuration dict: contains 'actions' (Actions[100])
        """
        self.check_token(token)
        self.__gateway_api.set_startup_action_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_dimmer_configuration(self, token, fields=None):
        """
        Get the dimmer_configuration.

        :param fields: The field of the dimmer_configuration to get. (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': dimmer_configuration dict: contains 'dim_memory' (Byte), \
        'dim_step' (Byte), 'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(config=self.__gateway_api.get_dimmer_configuration(fields))

    @cherrypy.expose
    def set_dimmer_configuration(self, token, config):
        """
        Set the dimmer_configuration.

        :param config: The dimmer_configuration to set
        :type config: dimmer_configuration dict: contains 'dim_memory' (Byte), \
        'dim_step' (Byte), 'dim_wait_cycle' (Byte), 'min_dim_level' (Byte)
        """
        self.check_token(token)
        self.__gateway_api.set_dimmer_configuration(json.loads(config))
        return self.__success()

    @cherrypy.expose
    def get_global_thermostat_configuration(self, token, fields=None):
        """
        Get the global_thermostat_configuration.

        :param fields: The field of the global_thermostat_configuration to get. \
        (None gets all fields)
        :type fields: Json encoded list of strings
        :returns: 'config': global_thermostat_configuration dict: contains \
        'outside_sensor' (Byte), 'pump_delay' (Byte), 'threshold_temp' (Temp)
        """
        self.check_token(token)
        fields = None if fields is None else json.loads(fields)
        return self.__success(
                config=self.__gateway_api.get_global_thermostat_configuration(fields))

    @cherrypy.expose
    def set_global_thermostat_configuration(self, token, config):
        """
        Set the global_thermostat_configuration.

        :param config: The global_thermostat_configuration to set
        :type config: global_thermostat_configuration dict: contains 'outside_sensor' (Byte), \
        'pump_delay' (Byte), 'threshold_temp' (Temp)
        """
        self.check_token(token)
        self.__gateway_api.set_global_thermostat_configuration(json.loads(config))
        return self.__success()

    ###### End of the the autogenerated configuration api

    @cherrypy.expose
    def get_power_modules(self, token):
        """ Get information on the power modules. The times format is a comma seperated list of
        HH:MM formatted times times (index 0 = start Monday, index 1 = stop Monday,
        index 2 = start Tuesday, ...).

        :returns: 'modules': list of dictionaries with the following keys: 'id', 'name', \
        'address', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', \
        'input7', 'sensor0', 'sensor1', 'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', \
        'sensor7', 'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        self.check_token(token)
        return self.__success(modules=self.__gateway_api.get_power_modules())

    @cherrypy.expose
    def set_power_modules(self, token, modules):
        """ Set information for the power modules.

        :param modules: json encoded list of dicts with keys: 'id', 'name', 'input0', 'input1', \
        'input2', 'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', \
        'sensor2', 'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', \
        'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__gateway_api.set_power_modules(json.loads(modules)))

    @cherrypy.expose
    def get_realtime_power(self, token):
        """ Get the realtime power measurements.

        :returns: module id as the keys: [voltage, frequency, current, power].
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.get_realtime_power)

    @cherrypy.expose
    def get_total_energy(self, token):
        """ Get the total energy (Wh) consumed by the power modules.

        :returns: modules id as key: [day, night].
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.get_total_energy)

    @cherrypy.expose
    def start_power_address_mode(self, token):
        """ Start the address mode on the power modules. """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.start_power_address_mode)

    @cherrypy.expose
    def stop_power_address_mode(self, token):
        """ Stop the address mode on the power modules. """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.stop_power_address_mode)

    @cherrypy.expose
    def in_power_address_mode(self, token):
        """ Check if the power modules are in address mode.

        :returns: 'address_mode': Boolean
        """
        self.check_token(token)
        return self.__wrap(self.__gateway_api.in_power_address_mode)

    @cherrypy.expose
    def set_power_voltage(self, token, module_id, voltage):
        """ Set the voltage for a given module.

        :param module_id: The id of the power module.
        :type module_id: Byte
        :param voltage: The voltage to set for the power module.
        :type voltage: Float
        """
        self.check_token(token)
        return self.__wrap(
                lambda: self.__gateway_api.set_power_voltage(int(module_id), float(voltage)))

    @cherrypy.expose
    def get_pulse_counter_status(self, token):
        """ Get the pulse counter values.

        :returns: 'counters': array with the 8 pulse counter values.
        """
        self.check_token(token)
        return self.__success(counters=self.__gateway_api.get_pulse_counter_status())

    @cherrypy.expose
    def get_version(self, token):
        """ Get the version of the openmotics software.

        :returns: 'version': String (a.b.c).
        """
        self.check_token(token)
        config = ConfigParser.ConfigParser()
        config.read(constants.get_config_file())
        return self.__success(version=str(config.get('OpenMotics', 'version')))

    @cherrypy.expose
    def update(self, token, version, md5, update_data):
        """ Perform an update.

        :param version: the new version number.
        :type version: String
        :param md5: the md5 sum of update_data.
        :type md5: String
        :param update_data: a tgz file containing the update script (update.sh) and data.
        :type update_data: multipart/form-data encoded byte string.
        """
        self.check_token(token)
        update_data = update_data.file.read()

        if not os.path.exists(constants.get_update_dir()):
            os.mkdir(constants.get_update_dir())

        update_file = open(constants.get_update_file(), "wb")
        update_file.write(update_data)
        update_file.close()

        output_file = open(constants.get_update_output_file(), "w")
        output_file.write('\n')
        output_file.close()

        subprocess.Popen(constants.get_update_cmd(version, md5), close_fds=True)

        return self.__success()

    @cherrypy.expose
    def get_update_output(self, token):
        """ Get the output of the last update.

        :returns: 'output': String with the output from the update script.
        """
        self.check_token(token)

        output_file = open(constants.get_update_output_file(), "r")
        output = output_file.read()
        output_file.close()

        return self.__success(output=output)

    @cherrypy.expose
    def set_timezone(self, token, timezone):
        """ Set the timezone for the gateway.

        :param timezone: in format 'Continent/City'.
        :type timezone: String
        """
        self.check_token(token)

        timezone_file_path = "/usr/share/zoneinfo/" + timezone
        if os.path.isfile(timezone_file_path):
            if os.path.exists(constants.get_timezone_file()):
                os.remove(constants.get_timezone_file())

            os.symlink(timezone_file_path, constants.get_timezone_file())

            self.__gateway_api.sync_master_time()
            return self.__success()
        else:
            return self.__error("Could not find timezone '" + timezone + "'")

    @cherrypy.expose
    def get_timezone(self, token):
        """ Get the timezone for the gateway.

        :returns: 'timezone': the timezone in 'Continent/City' format (String).
        """
        self.check_token(token)

        path = os.path.realpath(constants.get_timezone_file())
        if path.startswith("/usr/share/zoneinfo/"):
            return self.__success(timezone=path[20:])
        else:
            return self.__error("Could not determine timezone.")

    @cherrypy.expose
    def do_url_action(self, token, url, method='GET', headers=None, data=None, auth=None,
                      timeout=10):
        """ Execute an url action.

        :param url: The url to fetch.
        :type url: String
        :param method: (optional) The http method (defaults to GET).
        :type method: String
        :param headers: (optional) The http headers to send (format: json encoded dict)
        :type headers: String
        :param data: (optional) Bytes to send in the body of the request.
        :type data: String
        :param auth: (optional) Json encoded tuple (username, password).
        :type auth: String
        :param timeout: (optional) Timeout in seconds for the http request (default = 10 sec).
        :type timeout: Integer
        :returns: 'headers': response headers, 'data': response body.
        """
        self.check_token(token)

        try:
            headers = json.loads(headers) if headers != None else None
            auth = json.loads(auth) if auth != None else None

            request = requests.request(method, url, headers=headers, data=data, auth=auth,
                                 timeout=timeout)

            if request.status_code == requests.codes.ok:
                return self.__success(headers=request.headers._store, data=request.text)
            else:
                return self.__error("Got bad resonse code: %d" % request.status_code)
        except Exception as exception:
            return self.__error("Got exception '%s'" % str(exception))

    @cherrypy.expose
    def schedule_action(self, token, timestamp, action):
        """ Schedule an action at a given point in the future. An action can be any function of the
        OpenMotics webservice. The action is JSON encoded dict with keys: 'type', 'action',
        'params' and 'description'. At the moment 'type' can only be 'basic'. 'action' contains
        the name of the function on the webservice. 'params' is a dict maps the names of the
        parameters given to the function to their desired values. 'description' can be used to
        identify the scheduled action.

        :param timestamp: UNIX timestamp.
        :type timestamp: Integer.
        :param action: JSON encoded dict (see above).
        :type action: String.
        """
        self.check_token(token)
        timestamp = int(timestamp)
        action = json.loads(action)

        if not ('type' in action and action['type'] == 'basic' and 'action' in action):
            self.__error("action does not contain the required keys 'type' and 'action'")
        else:
            func_name = action['action']
            if func_name in WebInterface.__dict__:
                func = WebInterface.__dict__[func_name]
                if 'exposed' in func.__dict__ and func.exposed == True:
                    params = action.get('params', {})

                    args = inspect.getargspec(func).args
                    args = [arg for arg in args if arg != "token" and arg != "self"]

                    if len(args) != len(params):
                        return self.__error("The number of params (%d) does not match the number "
                                            "of arguments (%d) for function %s" %
                                            (len(params), len(args), func_name))

                    bad_args = [arg for arg in args if arg not in params]
                    if len(bad_args) > 0:
                        return self.__error("The following param are missing for function %s: %s" %
                                            (func_name, str(bad_args)))
                    else:
                        description = action.get('description', '')
                        action = json.dumps({'type' : 'basic', 'action': func_name,
                                             'params': params})

                        self.__scheduling_controller.schedule_action(timestamp, description,
                                                                     action)

                        return self.__success()

            return self.__error("Could not find function WebInterface.%s" % func_name)

    @cherrypy.expose
    def list_scheduled_actions(self, token):
        """ Get a list of all scheduled actions.

        :returns: 'actions': a list of dicts with keys: 'timestamp', 'from_now', 'id', \
        'description' and 'action'. 'timestamp' is the UNIX timestamp when the action will be \
        executed. 'from_now' is the number of seconds until the action will be scheduled. 'id' \
        is a unique integer for the scheduled action. 'description' contains a user set \
        description for the action. 'action' contains the function and params that will be \
        used to execute the scheduled action.
        """
        self.check_token(token)
        now = time.time()
        actions = self.__scheduling_controller.list_scheduled_actions()
        for action in actions:
            action['from_now'] = action['timestamp'] - now

        return self.__success(actions=actions)

    @cherrypy.expose
    def remove_scheduled_action(self, token, id):
        """ Remove a scheduled action when the id of the action is given.

        :param id: the id of the scheduled action to remove.
        :type id: Integer
        """
        self.check_token(token)
        self.__scheduling_controller.remove_scheduled_action(id)
        return self.__success()

    def __exec_scheduled_action(self, action):
        """ Callback for the SchedulingController executing a scheduled actions.

        :param action: JSON encoded action.
        """
        action = json.loads(action)
        func_name = action['action']
        kwargs = action['params']
        kwargs['self'] = self
        kwargs['token'] = None

        if func_name in WebInterface.__dict__:
            try:
                WebInterface.__dict__[func_name](**kwargs)
            except:
                LOGGER.exception("Exception while executing scheduled action")
        else:
            LOGGER.error("Could not find function WebInterface.%s", func_name)

    def __wrap(self, func):
        """ Wrap a gateway_api function and catches a possible Exception.

        :returns: {'success': False, 'msg': ...} on Exception, otherwise {'success': True, ...}
        """
        try:
            ret = func()
        except Exception as exception:
            traceback.print_exc()
            return self.__error(str(exception))
        else:
            return self.__success(**ret)

    @cherrypy.expose
    def get_plugins(self, token):
        """ Get the installed plugins.

        :returns: 'plugins': dict with name, version and interfaces where name and version \
        are strings and interfaces is a list of tuples (interface, version) which are both strings.
        """
        self.check_token(token)
        plugins = self.__plugin_controller.get_plugins()
        ret = [{'name' : p.name, 'version' : p.version, 'interfaces' : p.interfaces}
               for p in plugins]
        return self.__success(plugins=ret)

    @cherrypy.expose
    def get_plugin_logs(self, token):
        """ Get the logs for all plugins.

        :returns: 'logs': dict with the names of the plugins as keys and the logs (String) as \
        value.
        """
        self.check_token(token)
        return self.__success(logs=self.__plugin_controller.get_logs())

    @cherrypy.expose
    def install_plugin(self, token, md5, package_data):
        """ Install a new plugin. The package_data should include a __init__.py file and
        will be installed in /opt/openmotics/python/plugins/<name>.

        :param name: Name of the plugin to install.
        :type name: String
        :param version: Version of the plugin to install.
        :type version: String
        :param md5: md5 sum of the package_data.
        :type md5: String
        :param update_data: a tgz file containing the content of the plugin package.
        :type update_data: multipart/form-data encoded byte string.
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__plugin_controller.install_plugin(
                                                                md5, package_data.file.read()))

    @cherrypy.expose
    def remove_plugin(self, token, name):
        """ Remove a plugin. This removes the package data and configuration data of the plugin.

        :param name: Name of the plugin to remove.
        :param type: String
        """
        self.check_token(token)
        return self.__wrap(lambda: self.__plugin_controller.remove_plugin(name))


class WebService(object):
    """ The web service serves the gateway api over http. """

    name = 'web'

    def __init__(self, webinterface):
        self.__webinterface = webinterface
        self.__https_server = None
        self.__http_server = None

    def run(self):
        """ Run the web service: start cherrypy. """
        cherrypy.tree.mount(self.__webinterface,
                            config={'/static' :
                                          {'tools.staticdir.on' : True,
                                           'tools.staticdir.dir' : '/opt/openmotics/static'},
                                    '/' : {'tools.timestampFilter.on' : True,
                                           'tools.sessions.on' : True,
                                           'tools.sessions.storage_type' : 'ram',
                                           'tools.sessions.timeout' : 60}
                                   }
                            )

        cherrypy.server.unsubscribe()

        self.__https_server = cherrypy._cpserver.Server()
        self.__https_server.socket_port = 443
        self.__https_server._socket_host = '0.0.0.0'
        self.__https_server.socket_timeout = 60
        self.__https_server.ssl_module = 'pyopenssl'
        self.__https_server.ssl_certificate = constants.get_ssl_certificate_file()
        self.__https_server.ssl_private_key = constants.get_ssl_private_key_file()
        self.__https_server.subscribe()

        self.__http_server = cherrypy._cpserver.Server()
        self.__http_server.socket_port = 80
        self.__http_server._socket_host = '127.0.0.1'
        self.__http_server.socket_timeout = 60
        self.__http_server.subscribe()

        cherrypy.engine.autoreload_on = False

        cherrypy.engine.start()
        cherrypy.engine.block()

    def start(self):
        """ Start the web service in a new thread. """
        thread = threading.Thread(target=self.run)
        thread.setName("Web service thread")
        thread.daemon = True
        thread.start()

    def stop(self):
        """ Stop the web service. """
        cherrypy.engine.exit() ## Shutdown the cherrypy server: no new requests
        if self.__https_server is not None:
            self.__https_server.stop()
        if self.__http_server is not None:
            self.__http_server.stop()
