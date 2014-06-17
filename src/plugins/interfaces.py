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

""" Contains the definition of the plugin interfaces. """
import inspect

from plugins.base import PluginException

class PluginInterface(object):
    """ Definition of a plugin interface. Contains a name, version and a list
    of PluginMethods defined by the interface.
    """

    def __init__(self, name, version, methods):
        """ Default constructor.

        :param name: Name of the interface
        :type name: String
        :param version: Version of the interface
        :type version: String
        :param methods: The methods defined by the interface
        :type methods: list of PluginMethods
        """
        self.name = name
        self.version = version
        self.methods = methods


class PluginMethod(object):
    """ Defines a method. Contains the name of the method, whether authentication
    is required for the method and the arguments for the method.
    """

    def __init__(self, name, auth, arguments):
        """ Default constructor.

        :param name: Name of the method
        :type name: String
        :param auth: Whether authentication is required for the method
        :type auth: boolean
        :param arguments: list of the names of the arguments
        :type arguments: list of strings
        """
        self.name = name
        self.auth = auth
        self.arguments = arguments


INTERFACES = [
    PluginInterface("webui", "1.0", [
        PluginMethod("html_index", True, [])
    ]),

    PluginInterface("config", "1.0", [
        PluginMethod("get_config_description", True, []),
        PluginMethod("get_config", True, []),
        PluginMethod("set_config", True, ["config"])
    ]),
]


def get_interface(name, version):
    """ Get the PluginInterface with a given name and version, None if
    it doesn't exist. """
    for interface in INTERFACES:
        if name == interface.name and version == interface.version:
            return interface

    return None


def check_interface(plugin, interface):
    """ Check if the methods defined by the interface are present on the plugin.

    :param plugin: The plugin to check.
    :type plugin: OMPluginBase class.
    :param interface: The plugin to check.
    :type interface: PluginInterface object.
    :raises: PluginExcpetion if a method defined by the interface is not present.
    """
    plugin_name = plugin.name

    for method in interface.methods:
        plugin_method = getattr(plugin, method.name, None)

        if plugin_method is None or not callable(plugin_method):
            raise PluginException("Plugin '%s' has no method named '%s'" %
                                  (plugin_name, method.name))

        elif not (hasattr(plugin_method, 'exposed') and hasattr(plugin_method, 'auth') and
                  hasattr(plugin_method, 'orig')):
            raise PluginException("Plugin '%s' does not expose method '%s'" %
                                  (plugin_name, method.name))

        elif plugin_method.auth != method.auth:
            raise PluginException("Plugin '%s': authentication for method '%s' does not match the "
                                  "interface authentication (%s required)." %
                                  (plugin_name, method.name, method.auth))

        else:
            argspec = inspect.getargspec(plugin_method.orig)
            if len(argspec.args) == 0 or argspec.args[0] != "self":
                raise PluginException("Method '%s' on plugin '%s' lacks 'self' as first argument."
                                      % (method.name, plugin_name))

            if argspec.args[1:] != method.arguments:
                raise PluginException(
                        "Plugin '%s': the arguments for method '%s': %s do not match the interface"
                        " arguments: %s." % (plugin_name, method.name, argspec.args[1:],
                                             method.arguments))


def check_interfaces(plugin):
    """ Check the interfaces of a plugin. Raises a PluginException if there are problems
    with the interfaces on the plugin. Possible problems are: the interface was not found,
    the methods defined by the interface are not present.

    :param plugin: The plugin to check.
    :type plugin: OMPluginBase class.
    :raises: PluginException
    """
    if not isinstance(plugin.interfaces, list):
        raise PluginException("The interfaces attribute on plugin '%s' is not a list." %
                              plugin.name)
    else:
        for i in plugin.interfaces:
            if not isinstance(i, tuple) or len(i) != 2:
                raise PluginException("Interface '%s' on plugin '%s' is not a tuple of "
                                      "(name, version)." % (i, plugin.name))

            (name, version) = i
            interface = get_interface(name, version)
            if interface is None:
                raise PluginException("Interface '%s' with version '%s' was not found." %
                                      (name, version))
            else:
                check_interface(plugin, interface)
