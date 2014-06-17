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
Tests for plugins.interfaces.
Created on Dec 30, 2013

@author: fryckbos
'''
import unittest

from plugins.base import OMPluginBase, PluginException, om_expose
from plugins.interfaces import check_interfaces

class CheckInterfacesTest(unittest.TestCase):
    """ Tests for check_interfaces. """

    def test_no_interfaces(self):
        """ Test a plugin without interfaces. """
        class P1(OMPluginBase):
            """ Plugin without interfaces. """
            name = "P1"
            version = "1.0"
            interfaces = []

        check_interfaces(P1) ## Should not raise exceptions

    def test_wrong_interface_format(self):
        """ Test a plugin with the wrong interface format. """
        class P1(OMPluginBase):
            """ Plugin with invalid interface. """
            name = "P1"
            version = "1.0"
            interfaces = "interface1"

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("The interfaces attribute on plugin 'P1' is not a list.",
                              str(exception))

        class P2(OMPluginBase):
            """ Plugin with invalid interface. """
            name = "P2"
            version = "1.0"
            interfaces = ["interface1"]

        try:
            check_interfaces(P2)
        except PluginException as exception:
            self.assertEquals("Interface 'interface1' on plugin 'P2' is not a tuple of "
                              "(name, version).", str(exception))

        class P3(OMPluginBase):
            """ Plugin with invalid interface. """
            name = "P3"
            version = "1.0"
            interfaces = [("interface1")]

        try:
            check_interfaces(P3)
        except PluginException as exception:
            self.assertEquals("Interface 'interface1' on plugin 'P3' is not a tuple of "
                              "(name, version).", str(exception))

    def test_interface_not_found(self):
        """ Test a plugin with an interface that is not known. """
        class P1(OMPluginBase):
            """ Plugin with unknown interface. """
            name = "P1"
            version = "1.0"
            interfaces = [("myinterface", "2.0")]

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Interface 'myinterface' with version '2.0' was not found.",
                              str(exception))

    def test_missing_method_interface(self):
        """ Test a plugin with a missing method. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and missing methods. """
            name = "P1"
            version = "1.0"
            interfaces = [("webui", "1.0")]

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Plugin 'P1' has no method named 'html_index'", str(exception))

    def test_not_a_method(self):
        """ Test where a name of an interface method is used for something else. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and missing methods. """
            name = "P1"
            version = "1.0"
            interfaces = [("webui", "1.0")]
            html_index = "hello"

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Plugin 'P1' has no method named 'html_index'", str(exception))

    def test_not_exposed_interface(self):
        """ Test a non-exposed method on a plugin. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and unexposed methods. """
            name = "P1"
            version = "1.0"
            interfaces = [("webui", "1.0")]

            def html_index(self):
                """ Be nice and say hello. """
                return "hello"

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Plugin 'P1' does not expose method 'html_index'", str(exception))

    def test_wrong_authentication_interface(self):
        """ Test a plugin with wrong authentication on a method. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and methods without authentication. """
            name = "P1"
            version = "1.0"
            interfaces = [("webui", "1.0")]

            @om_expose(auth=False)
            def html_index(self):
                """ Be nice and say hello. """
                return "hello"

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Plugin 'P1': authentication for method 'html_index' does not match "
                              "the interface authentication (True required).", str(exception))

    def test_wrong_arguments(self):
        """ Test a plugin with wrong arguments to a method. """
        class P1(OMPluginBase):
            """ Plugin with interface and methods with the wrong arguments. """
            name = "P1"
            version = "1.0"
            interfaces = [("config", "1.0")]

            @om_expose(auth=True)
            def get_config_description(self):
                """ Method arguments are fine. """
                pass

            @om_expose(auth=True)
            def get_config(self):
                """ Method arguments are fine. """
                pass

            @om_expose(auth=True)
            def set_config(self, test):
                """ Method arguments: expected config instead of test. """
                pass

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Plugin 'P1': the arguments for method 'set_config': ['test'] do "
                              "not match the interface arguments: ['config'].", str(exception))

    def test_missing_self(self):
        """ Test a plugin that is missing 'self' for a method. """
        class P1(OMPluginBase):
            """ Plugin with interface method without self. """
            name = "P1"
            version = "1.0"
            interfaces = [("webui", "1.0")]

            @om_expose(auth=True)
            def html_index(): # pylint: disable=E0211
                """ Without self. """
                pass

        try:
            check_interfaces(P1)
        except PluginException as exception:
            self.assertEquals("Method 'html_index' on plugin 'P1' lacks 'self' as first "
                              "argument.", str(exception))

    def test_ok(self):
        """ Test an interface check that succeeds. """
        class P1(OMPluginBase):
            """ Plugin with multiple interfaces that are well implemented. """
            name = "P1"
            version = "1.0"
            interfaces = [("config", "1.0"), ("webui", "1.0")]

            @om_expose(auth=True)
            def get_config_description(self):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def get_config(self):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def set_config(self, config):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def html_index(self):
                """ No implementation. """
                pass

        check_interfaces(P1)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
