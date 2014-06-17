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
Tests for plugins.base.
Created on Dec 31, 2013

@author: fryckbos
'''
import unittest

import os
import shutil

import plugins
BASE_PATH = os.path.dirname(plugins.__file__)

from plugins.base import PluginConfigChecker, PluginException

class PluginControllerTest(unittest.TestCase):
    """ Tests for the PluginController. """

    def create_plugin(self, name, code):
        """ Create a plugin with a given name and the provided code. """
        path = "%s/%s" % (BASE_PATH, name)
        os.makedirs(path)

        code_file = open("%s/main.py" % path, "w")
        code_file.write(code)
        code_file.close()

        init_file = open("%s/__init__.py" % path, "w")
        init_file.close()

    def destroy_plugin(self, name):
        """ Remove the code for a plugin created by create_plugin. """
        path = "%s/%s" % (BASE_PATH, name)
        if os.path.exists(path):
            shutil.rmtree(path)

    def test_get_one_plugin(self):
        """ Test getting one plugin in the plugins package. """
        try:
            self.create_plugin("test", """
from plugins.base import *

class P1(OMPluginBase):
    name = "P1"
    version = "1.0.0"
    interfaces = []
""")
            from plugins.base import PluginController

            controller = PluginController(None)
            plugin_list = controller.get_plugins()
            self.assertEquals(1, len(plugin_list))
            self.assertEquals("P1", plugin_list[0].name)
        finally:
            self.destroy_plugin("test")

    def test_get_two_plugins(self):
        """ Test getting two plugins in the plugins package. """
        try:
            self.create_plugin("test1", """
from plugins.base import *

class P1(OMPluginBase):
    name = "P1"
    version = "1.0.0"
    interfaces = []
""")

            self.create_plugin("test2", """
from plugins.base import *

class P2(OMPluginBase):
    name = "P2"
    version = "1.0.0"
    interfaces = []
""")

            from plugins.base import PluginController

            controller = PluginController(None)
            plugin_list = controller.get_plugins()
            self.assertEquals(2, len(plugin_list))

            self.assertEquals("P2", plugin_list[0].name)
            self.assertEquals("P1", plugin_list[1].name)
        finally:
            self.destroy_plugin("test1")
            self.destroy_plugin("test2")


    def test_get_special_methods(self):
        """ Test getting special methods on a plugin. """
        from plugins.base import OMPluginBase, om_expose, input_status, output_status, \
                                 background_task

        class P1(OMPluginBase):
            """ Plugin 1. """
            name = "P1"
            version = "0.1.0"
            interfaces = [("webui", "1.0")]

            def __init__(self, webservice, logger):
                OMPluginBase.__init__(self, webservice, logger)

            @om_expose(auth=True)
            def html_index(self):
                """ Nothing. """
                pass

            @om_expose(auth=False)
            def get_log(self):
                """ Nothing. """
                pass

            @input_status
            def input(self, input_status_inst):
                """ Nothing. """
                pass

            @output_status
            def output(self, output_status_inst):
                """ Nothing. """
                pass

            @background_task
            def run(self):
                """ Nothing. """
                pass

        from plugins.base import PluginController

        controller = PluginController(None)
        plugin1 = P1(None, None)

        ins = controller._get_special_methods(plugin1, "input_status")
        self.assertEquals(1, len(ins))
        self.assertEquals("input", ins[0].__name__)

        outs = controller._get_special_methods(plugin1, "output_status")
        self.assertEquals(1, len(outs))
        self.assertEquals("output", outs[0].__name__)

        bts = controller._get_special_methods(plugin1, "background_task")
        self.assertEquals(1, len(bts))
        self.assertEquals("run", bts[0].__name__)

    def test_check_plugin(self):
        """ Test the exception that can occur when checking a plugin. """
        from plugins.base import OMPluginBase, om_expose, input_status, output_status, \
                                 background_task

        from plugins.base import PluginController
        controller = PluginController(None)

        class P1(OMPluginBase):
            """ Plugin without name. """
            pass

        try:
            controller.check_plugin(P1)
        except PluginException as exception:
            self.assertEquals("attribute 'name' is missing from the plugin class", str(exception))

        class P2(OMPluginBase):
            """ Plugin with malformed name. """
            name = "malformed name"

        try:
            controller.check_plugin(P2)
        except PluginException as exception:
            self.assertEquals("Plugin name 'malformed name' is malformed: "
                              "can only contain letters, numbers and underscores.", str(exception))

        class P3(OMPluginBase):
            """ Plugin without version. """
            name = "test_name123"

        try:
            controller.check_plugin(P3)
        except PluginException as exception:
            self.assertEquals("attribute 'version' is missing from the plugin class",
                              str(exception))

        class P4(OMPluginBase):
            """ Plugin without interfaces. """
            name = "test"
            version = "1.0.0"

        try:
            controller.check_plugin(P4)
        except PluginException as exception:
            self.assertEquals("attribute 'interfaces' is missing from the plugin class",
                              str(exception))

        class P5(OMPluginBase):
            """ Valid plugin. """
            name = "test"
            version = "1.0.0"
            interfaces = []

        controller.check_plugin(P5)

        class P6(OMPluginBase):
            """ Plugin that violates the webui interface. """
            name = "test"
            version = "1.0.0"
            interfaces = [("webui", "1.0")]

        try:
            controller.check_plugin(P6)
        except PluginException as exception:
            self.assertEquals("Plugin 'test' has no method named 'html_index'", str(exception))

FULL_DESCR = [
    {'name' : 'hostname', 'type' : 'str', 'description': 'The hostname of the server.'},
    {'name' : 'port', 'type' : 'int', 'description': 'Port on the server.'},
    {'name' : 'use_auth', 'type' : 'bool', 'description': 'Use authentication while connecting.'},
    {'name' : 'password', 'type' : 'password', 'description': 'Your secret password.'},
    {'name' : 'enumtest', 'type' : 'enum',
     'description': 'Test for enum', 'choices': ['First', 'Second']},

    {'name' : 'outputs', 'type' : 'section', 'repeat' : True, 'min' : 1,
     'content' : [{'name' : 'output', 'type' : 'int'}]
    },

    {'name' : 'network', 'type' : 'nested_enum', 'choices' : [
        {'value': 'Facebook', 'content' : [{'name' : 'likes', 'type' : 'int'}]},
        {'value': 'Twitter', 'content' : [{'name' : 'followers', 'type' : 'int'}]}
    ]}
]

class PluginConfigCheckerTest(unittest.TestCase):
    """ Tests for the PluginConfigChecker. """

    def test_constructor(self):
        """ Test for the constructor. """
        PluginConfigChecker(FULL_DESCR)

    def test_constructor_error(self):
        """ Test with an invalid data type """
        try:
            PluginConfigChecker({'test' : 123})
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('list' in str(exception))

        try:
            PluginConfigChecker([{'test' : 123}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('name' in str(exception))

        try:
            PluginConfigChecker([{'name' : 123}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('name' in str(exception) and 'string' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'test'}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('type' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'test', 'type' : 123}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('type' in str(exception) and 'string' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'test', 'type' : 'something_else'}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('type' in str(exception) and 'something_else' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'test', 'type' : 'str', 'description': []}])
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('description' in str(exception) and 'string' in str(exception))

    def test_constructor_str(self):
        """ Test for the constructor for str. """
        PluginConfigChecker([{'name' : 'hostname', 'type' : 'str',
                              'description': 'The hostname of the server.'}])
        PluginConfigChecker([{'name' : 'hostname', 'type' : 'str'}])

        try:
            PluginConfigChecker([{'type' : 'str'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('name' in str(exception))

    def test_constructor_int(self):
        """ Test for the constructor for int. """
        PluginConfigChecker([{'name' : 'port', 'type' : 'int',
                              'description': 'Port on the server.'}])
        PluginConfigChecker([{'name' : 'port', 'type' : 'int'}])

        try:
            PluginConfigChecker([{'type' : 'int'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('name' in str(exception))

    def test_constructor_bool(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([{'name' : 'use_auth', 'type' : 'bool',
                              'description': 'Use authentication while connecting.'}])
        PluginConfigChecker([{'name' : 'use_auth', 'type' : 'bool'}])

        try:
            PluginConfigChecker([{'type' : 'bool'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('name' in str(exception))

    def test_constructor_password(self):
        """ Test for the constructor for bool. """
        PluginConfigChecker([{'name' : 'password', 'type' : 'password',
                              'description': 'A password.'}])
        PluginConfigChecker([{'name' : 'password', 'type' : 'password'}])

        try:
            PluginConfigChecker([{'type' : 'password'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('name' in str(exception))

    def test_constructor_enum(self):
        """ Test for the constructor for enum. """
        PluginConfigChecker([{'name' : 'enumtest', 'type' : 'enum', 'description': 'Test for enum',
                              'choices': ['First', 'Second']}])
        PluginConfigChecker([{'name' : 'enumtest', 'type' : 'enum',
                              'choices': ['First', 'Second']}])

        try:
            PluginConfigChecker([{'name' : 'enumtest', 'type' : 'enum', 'choices': 'First'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'list' in str(exception))

    def test_constructor_section(self):
        """ Test for the constructor for section. """
        PluginConfigChecker([{'name' : 'outputs', 'type' : 'section', 'repeat' : True, 'min' : 1,
                              'content' : [{'name' : 'output', 'type' : 'int'}]}])

        PluginConfigChecker([{'name' : 'outputs', 'type' : 'section', 'repeat' : False,
                              'content' : [{'name' : 'output', 'type' : 'int'}]}])

        PluginConfigChecker([{'name' : 'outputs', 'type' : 'section',
                              'content' : [{'name' : 'output', 'type' : 'int'}]}])

        try:
            PluginConfigChecker([{'name' : 'outputs', 'type' : 'section', 'repeat' : 'hello',
                                  'content' : [{'name' : 'output', 'type' : 'int'}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('repeat' in str(exception) and 'bool' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'outputs', 'type' : 'section', 'min' : 1,
                                  'content' : [{'name' : 'output', 'type' : 'int'}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('min' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'outputs', 'type' : 'section',
                                  'content' : 'error'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('content' in str(exception) and 'list' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'outputs', 'type' : 'section',
                                  'content' : [{'name' : 123}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('content' in str(exception) and 'name' in str(exception) \
                            and 'string' in str(exception))

    def test_constructor_nested_enum(self):
        """ Test for constructor for nested enum. """
        PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum', 'choices' : [
                               {'value': 'Facebook',
                                'content' : [{'name' : 'likes', 'type' : 'int'}]},
                               {'value': 'Twitter',
                                'content' : [{'name' : 'followers', 'type' : 'int'}]}
                            ]}])

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : 'test'}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'list' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : ['test']}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'dict' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum', 'choices' : [{}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'value' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : [{'value' : 123}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'value' in str(exception) \
                            and 'string' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : [{'value' : 'test'}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'content' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : [{'value' : 'test', 'content' : 'test'}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'content' in str(exception) \
                            and 'list' in str(exception))

        try:
            PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum',
                                  'choices' : [{'value' : 'test', 'content' : [{}]}]}])
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception) and 'content' in str(exception) \
                            and 'name' in str(exception))

    def test_check_config_error(self):
        """ Test check_config with an invalid data type """
        checker = PluginConfigChecker([{'name' : 'hostname', 'type' : 'str'}])

        try:
            checker.check_config('string')
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('dict' in str(exception))

        try:
            checker.check_config({})
            self.fail("Expected PluginException")
        except PluginException as exception:
            self.assertTrue('hostname' in str(exception))

    def test_check_config_str(self):
        """ Test check_config for str. """
        checker = PluginConfigChecker([{'name' : 'hostname', 'type' : 'str'}])
        checker.check_config({'hostname' : 'cloud.openmotics.com'})

        try:
            checker.check_config({'hostname' : 123})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('str' in str(exception))

    def test_check_config_int(self):
        """ Test check_config for int. """
        checker = PluginConfigChecker([{'name' : 'port', 'type' : 'int'}])
        checker.check_config({'port' : 123})

        try:
            checker.check_config({'port' : "123"})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('int' in str(exception))

    def test_check_config_bool(self):
        """ Test check_config for bool. """
        checker = PluginConfigChecker([{'name' : 'use_auth', 'type' : 'bool'}])
        checker.check_config({'use_auth' : True})

        try:
            checker.check_config({'use_auth' : 234543})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('bool' in str(exception))

    def test_check_config_password(self):
        """ Test check_config for bool. """
        checker = PluginConfigChecker([{'name' : 'password', 'type' : 'password'}])
        checker.check_config({'password' : 'test'})

        try:
            checker.check_config({'password' : 123})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('str' in str(exception))

    def test_check_config_section(self):
        """ Test check_config for section. """
        checker = PluginConfigChecker([{'name' : 'outputs', 'type' : 'section', 'repeat' : True,
                                    'min' : 1, 'content' : [{'name' : 'output', 'type' : 'int'}]}])

        checker.check_config({'outputs' : []})
        checker.check_config({'outputs' : [{'output' : 2}]})
        checker.check_config({'outputs' : [{'output' : 2}, {'output' : 4}]})

        try:
            checker.check_config({'outputs' : 'test'})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('list' in str(exception))

        try:
            checker.check_config({'outputs' : [{'test' : 123}]})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('section' in str(exception) and 'output' in str(exception))

    def test_check_config_nested_enum(self):
        """ Test check_config for nested_enum. """
        checker = PluginConfigChecker([{'name' : 'network', 'type' : 'nested_enum', 'choices' : [
                                     {'value': 'Facebook',
                                      'content' : [{'name' : 'likes', 'type' : 'int'}]},
                                     {'value': 'Twitter',
                                      'content' : [{'name' : 'followers', 'type' : 'int'}]}
                                    ]}])

        checker.check_config({'network' : ['Twitter', {'followers' : 3}]})
        checker.check_config({'network' : ['Facebook', {'likes' : 3}]})

        try:
            checker.check_config({'network' : 'test'})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('list' in str(exception))

        try:
            checker.check_config({'network' : []})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('list' in str(exception) and '2' in str(exception))

        try:
            checker.check_config({'network' : ['something else', {}]})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('choices' in str(exception))

        try:
            checker.check_config({'network' : ['Twitter', {}]})
            self.fail('Excepted exception')
        except PluginException as exception:
            self.assertTrue('nested_enum dict' in str(exception) and 'followers' in str(exception))

    def test_simple(self):
        """ Test a simple valid configuration. """
        checker = PluginConfigChecker([
            {'name' : 'log_inputs', 'type' : 'bool', 'description': 'Log the input data.'},
            {'name' : 'log_outputs', 'type' : 'bool', 'description': 'Log the output data.'}
        ])

        checker.check_config({'log_inputs' : True, 'log_outputs' : False})


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
