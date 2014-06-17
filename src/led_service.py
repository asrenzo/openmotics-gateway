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

""" Service that drives the leds and checks the switch on the front panel of the gateway.
This service allows other services to set the leds over dbus and check whether the
gateway is in authorized mode.
"""

import gobject

import dbus
import dbus.service
import dbus.mainloop.glib
import fcntl
import time
import urllib2

from threading import Thread
from ConfigParser import ConfigParser

import constants

I2C_DEVICE_BB = '/dev/i2c-2'  # Beaglebone
I2C_DEVICE_BBB = '/dev/i2c-1' #Beaglebone black

GPIO_INPUT_BUTTON_GW = 38   # Pin for the input button on the separate gateway module (deprecated)
GPIO_INPUT_BUTTON_GW_M = 26 # Pin for the input button on the gateway/master module (current) 

IOCTL_I2C_SLAVE = 0x0703
CODES = {'uart4':64, 'uart5':128, 'vpn':16, 'stat1':0, 'stat2':0, 'alive':1, 'cloud':4}
AUTH_CODE = 1 + 4 + 16 + 64 + 128

HOME = 75

ETH_LEFT = 60
ETH_RIGHT = 49

AUTH_LOOP = ['1', '0', '1', '0', '0', '0', '0', '0']


def is_beagle_bone_black():
    """ Use the total memory size to determine whether the code runs on a Beaglebone
    or on a Beaglebone Black. """
    meminfo = open('/proc/meminfo', 'r')
    mem_total = meminfo.readline()
    meminfo.close()
    return "510716 kB" in mem_total


def is_button_pressed(gpio_pin):
    """ Read the input button: returns True if the button is pressed, False if not. """
    fh_inp = open('/sys/class/gpio/gpio%d/value' % gpio_pin, 'r')
    line = fh_inp.read()
    fh_inp.close()
    return (int(line) == 0)


def detect_button(gpio_1, gpio_2):
    """ Detect which gpio pin is connected the input button. If the button is not connected, the
    pin will look as if the button is pressed. So if there is one input that is not pressed, it
    must be connected to the button. If both pins look pressed, it defaults to the first given
    gpio. """
    first_pressed = is_button_pressed(gpio_1)
    second_pressed = is_button_pressed(gpio_2)

    if not first_pressed:
        return gpio_1
    elif not second_pressed:
        return gpio_2
    else:
        return gpio_1


class StatusObject(dbus.service.Object):
    """ The StatusObject contains the methods exposed over dbus, the serial and network activity
    checkers and the 'authorized' button checker. """

    def __init__(self, bus, path, i2c_device, i2c_address, input_button):
        dbus.service.Object.__init__(self, bus, path)
        self.__i2c_device = i2c_device
        self.__i2c_address = i2c_address
        self.__input_button = input_button

        self.__network_enabled = False
        self.__network_activity = False
        self.__network_bytes = 0

        self.__serial_activity = {4: False, 5: False}
        self.__enabled_leds = {}
        self.__last_code = 0

        self.__times_pressed = 0
        self.__master_leds_thread = None
        self.__master_leds_turn_on = True
        self.__master_leds_on = False
        self.__master_leds_timeout = 0

        self.__authorized_mode = False
        self.__authorized_timeout = 0
        self.__authorized_index = 0

        self.clear_leds()

    def start(self):
        """ Start the master LEDs thread. """
        self.__master_leds_thread = Thread(target=self.__drive_master_leds)
        self.__master_leds_thread.daemon = True
        self.__master_leds_thread.start()

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='')
    def clear_leds(self):
        """ Turn all LEDs off. """
        for led in CODES:
            self.__enabled_leds[led] = False
        self.__set_output()

    @dbus.service.method("com.openmotics.status", in_signature='sb', out_signature='')
    def set_led(self, led_name, enable):
        """ Set the state of a LED, enabled means LED on in this context. """
        self.__enabled_leds[led_name] = enable
        self.__set_output()

    @dbus.service.method("com.openmotics.status", in_signature='s', out_signature='')
    def toggle_led(self, led_name):
        """ Toggle the state of a LED. """
        self.__enabled_leds[led_name] = not self.__enabled_leds[led_name]
        self.__set_output()

    @dbus.service.method("com.openmotics.status", in_signature='i', out_signature='')
    def serial_activity(self, port):
        """ Report serial activity on the given serial port. Port is 4 or 5. """
        self.__serial_activity[port] = True

    @dbus.service.method("com.openmotics.status", in_signature='', out_signature='b')
    def in_authorized_mode(self):
        """ Returns whether the gateway is in authorized mode. Authorized mode is enabled when the
        button on the top panel is pushed and lasts for 60 seconds. """
        return self.__authorized_mode

    def __get_i2c_code(self):
        """ Generates the i2c code for the LEDs. """
        code = 0
        for led in CODES:
            if self.__enabled_leds[led] == True:
                code |= CODES[led]

        if self.__authorized_mode: # Light all leds in authorized mode
            code |= AUTH_CODE

        return (~ code) & 255

    def __set_output(self):
        """ Set the LEDs using the current status. """
        try:
            new_code = self.__get_i2c_code()
            if new_code != self.__last_code:
                self.__last_code = new_code
                i2c = open(self.__i2c_device, 'r+', 1)
                fcntl.ioctl(i2c, IOCTL_I2C_SLAVE, self.__i2c_address)
                i2c.write(chr(self.__get_i2c_code()))
                i2c.close()
        except Exception as exception:
            print "Error while writing to i2c: ", exception

    def serial(self):
        """ Function that toggles the UART LEDs in case there was activity on the port.
        This function registers itself with the gobject creating a loop that runs every 100 ms.
        """
        for uart in [4, 5]:
            if self.__serial_activity[uart]:
                self.toggle_led('uart' + str(uart))
            else:
                self.set_led('uart' + str(uart), False)
            self.__serial_activity[uart] = False
        gobject.timeout_add(100, self.serial)

    def network(self):
        """ Function that set the LEDs on the ethernet port using the statistics from /proc/net.
        This function registers itself with the gobject creating a loop that runs every 100 ms.
        """
        fh_up = open('/sys/class/net/eth0/carrier', 'r')
        line = fh_up.read()
        fh_up.close()
        self.__network_enabled = int(line) == 1

        fh_stat = open('/proc/net/dev', 'r')
        for line in fh_stat.readlines():
            if 'eth0' in line:
                parts = line.split()
                if len(parts) == 17:
                    received = parts[1]
                    transmitted = parts[9]
                elif len(parts) == 16:
                    (_, received) = tuple(parts[0].split(':'))
                    transmitted = parts[8]
                new_bytes = received + transmitted
                if self.__network_bytes != new_bytes:
                    self.__network_bytes = new_bytes
                    self.__network_activity = not self.__network_activity
                else:
                    self.__network_activity = False
        fh_stat.close()

        self.__set_network()
        gobject.timeout_add(100, self.network)

    def __set_network(self):
        """ Set the LEDs on the ethernet port using the current state. """
        fh_r = open("/sys/class/gpio/gpio%i/value" % ETH_LEFT, 'w')
        fh_r.write('1' if self.__network_enabled else '0')
        fh_r.close()

        fh_l = open("/sys/class/gpio/gpio%i/value" % ETH_RIGHT, 'w')
        fh_l.write('1' if self.__network_activity else '0')
        fh_l.close()

    def input(self):
        """ Read the input button on the top panel. Enables the master LEDs when pressed shortly,
        enables authorized mode for 60 seconds when the button is pushed for 5 seconds.
        This function registers itself with the gobject creating a loop that runs every 100 ms.
        While the gateway is in authorized mode, the input button is not checked.
        """
        if is_button_pressed(self.__input_button):
            if not self.__master_leds_on:
                self.__master_leds_turn_on = True

            self.__times_pressed += 1
            if self.__times_pressed == 50:
                self.__authorized_mode = True
                self.__authorized_timeout = time.time() + 60
                gobject.timeout_add(100, self.__authorized)
            else:
                gobject.timeout_add(100, self.input)
        else:
            self.__times_pressed = 0
            gobject.timeout_add(100, self.input)

    def __authorized(self):
        """ The authorized loop runs when the gateway is in authorized mode: it makes the LED in the
        OpenMotics logo flash and checks whether the timeout for the authorized mode is reached.
        """
        if time.time() > self.__authorized_timeout:
            self.__authorized_mode = False
            self.__authorized_timeout = 0
            self.__set_home('1')
            gobject.timeout_add(100, self.input)
        else:
            self.__set_home(AUTH_LOOP[self.__authorized_index])
            self.__authorized_index = (self.__authorized_index + 1) % len(AUTH_LOOP)
            gobject.timeout_add(100, self.__authorized)

    def __set_home(self, value):
        """ Set the status of the LED in the OpenMotics logo. """
        fh_home = open("/sys/class/gpio/gpio%i/value" % HOME, 'w')
        fh_home.write(value)
        fh_home.close()

    def __drive_master_leds(self):
        """ Turns the master LEDs on or off if required. """
        while True:
            if self.__master_leds_turn_on:
                if self.__master_leds_on == False:
                    self.__master_set_leds(True)
            else:
                if self.__master_leds_on == True and time.time() > self.__master_leds_timeout:
                    self.__master_set_leds(False)

            time.sleep(0.2)

    def __master_set_leds(self, status):
        """ Set the status of the leds on the master. """
        try:
            uri = "https://127.0.0.1/set_master_status_leds?token=None&status=" + str(status)
            handler = urllib2.urlopen(uri, timeout=60.0)
            _ = handler.read()
            handler.close()

            self.__master_leds_on = status
            if status == True:
                self.__master_leds_turn_on = False
                self.__master_leds_timeout = time.time() + 120

        except Exception as exception:
            print "Exception during setting leds : ", exception


def main():
    """ The main function runs a loop that waits for dbus calls, drives the leds and reads the
    switch. """
    config = ConfigParser()
    config.read(constants.get_config_file())

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    system_bus = dbus.SystemBus()
    _ = dbus.service.BusName("com.openmotics.status", system_bus) # Initializes the bus.

    i2c_device = I2C_DEVICE_BBB if is_beagle_bone_black() else I2C_DEVICE_BB
    i2c_address = int(config.get('OpenMotics', 'leds_i2c_address'), 16)

    gpio_input = detect_button(GPIO_INPUT_BUTTON_GW_M, GPIO_INPUT_BUTTON_GW)

    status = StatusObject(system_bus, '/com/openmotics/status', i2c_device, i2c_address, gpio_input)
    status.start()

    mainloop = gobject.MainLoop()
    gobject.timeout_add(100, status.network)
    gobject.timeout_add(100, status.serial)
    gobject.timeout_add(100, status.input)

    print "Running led service."
    mainloop.run()


if __name__ == '__main__':
    main()
