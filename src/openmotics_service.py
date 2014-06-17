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
The main module for the OpenMotics

Created on Sep 23, 2012

@author: fryckbos
'''
import logging
import sys
import time
import threading

from serial import Serial
from signal import signal, SIGTERM
from ConfigParser import ConfigParser

import constants

from serial_utils import RS485

from gateway.webservice import WebInterface, WebService
from gateway.gateway_api import GatewayApi
from gateway.users import UserController

from bus.led_service import LedService

from master.maintenance import MaintenanceService
from master.master_communicator import MasterCommunicator
from master.passthrough import PassthroughService

from power.power_communicator import PowerCommunicator
from power.power_controller import PowerController

from plugins.base import PluginController

def setup_logger():
    """ Setup the OpenMotics logger. """
    logger = logging.getLogger("openmotics")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def led_driver(led_service, master_communicator, power_communicator):
    """ Blink the serial leds if necessary. """
    master = (0, 0)
    power = (0, 0)

    while True:
        if master[0] != master_communicator.get_bytes_read() \
                or master[1] != master_communicator.get_bytes_written():
            led_service.serial_activity(5)

        if power[0] != power_communicator.get_bytes_read() \
                or power[1] != power_communicator.get_bytes_written():
            led_service.serial_activity(4)

        master = (master_communicator.get_bytes_read(), master_communicator.get_bytes_written())
        power = (power_communicator.get_bytes_read(), power_communicator.get_bytes_written())
        time.sleep(0.100)

def main():
    """ Main function. """
    config = ConfigParser()
    config.read(constants.get_config_file())

    defaults = {'username' : config.get('OpenMotics', 'cloud_user'),
                'password': config.get('OpenMotics', 'cloud_pass')}

    user_controller = UserController(constants.get_user_database_file(), defaults, 3600)

    led_service = LedService()

    controller_serial_port = config.get('OpenMotics', 'controller_serial')
    passthrough_serial_port = config.get('OpenMotics', 'passthrough_serial')
    power_serial_port = config.get('OpenMotics', 'power_serial')

    controller_serial = Serial(controller_serial_port, 115200)
    passthrough_serial = Serial(passthrough_serial_port, 19200)
    power_serial = RS485(Serial(power_serial_port, 115200))

    master_communicator = MasterCommunicator(controller_serial)
    master_communicator.start()

    power_controller = PowerController(constants.get_power_database_file())

    power_communicator = PowerCommunicator(power_serial, power_controller)
    power_communicator.start()

    gateway_api = GatewayApi(master_communicator, power_communicator, power_controller)

    maintenance_service = MaintenanceService(gateway_api, constants.get_ssl_private_key_file(),
                                             constants.get_ssl_certificate_file())

    passthrough_service = PassthroughService(master_communicator, passthrough_serial)
    passthrough_service.start()

    web_interface = WebInterface(user_controller, gateway_api,
                                constants.get_scheduling_database_file(), maintenance_service,
                                led_service.in_authorized_mode)

    plugin_controller = PluginController(web_interface)
    plugin_controller.start_plugins()

    web_interface.set_plugin_controller(plugin_controller)
    gateway_api.set_plugin_controller(plugin_controller)

    web_service = WebService(web_interface)
    web_service.start()

    led_service.set_led('stat2', True)

    led_thread = threading.Thread(target=led_driver, args=(led_service,
                                                           master_communicator, power_communicator))
    led_thread.setName("Serial led driver thread")
    led_thread.daemon = True
    led_thread.start()

    def stop(signum, frame):
        """ This function is called on SIGTERM. """
        sys.stderr.write("Shutting down")
        led_service.set_led('stat2', False)
        web_service.stop()

    signal(SIGTERM, stop)


if __name__ == "__main__":
    setup_logger()
    main()

