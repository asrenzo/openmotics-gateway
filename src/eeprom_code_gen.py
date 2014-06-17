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

''' Script to generate code based on the eeprom models. '''

import re
import sys

from master.eeprom_models import OutputConfiguration, InputConfiguration, ThermostatConfiguration,\
              SensorConfiguration, PumpGroupConfiguration, GroupActionConfiguration, \
              ScheduledActionConfiguration, PulseCounterConfiguration, StartupActionConfiguration,\
              DimmerConfiguration, GlobalThermostatConfiguration

def model_name_u(model_name):
    """ Get the model name with underscores. """
    output1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', model_name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', output1).lower()


def model_dict_descr_read(model):
    """ Get a description for the model dict (for read operations). """
    fields = []

    if model.has_id():
        fields.append("'id' (Id)")

    for field in model.get_fields():
        fields.append("'%s' (%s)" % (field[0], field[1].get_name()))

    return "%s dict: contains %s" % (model_name_u(model.get_name()), ", ".join(fields))


def model_dict_descr_write(model):
    """ Get a description for the model dict (for write operations). """
    fields = []

    if model.has_id():
        fields.append("'id' (Id)")

    for field in model.get_fields():
        if field[1].is_writable():
            fields.append("'%s' (%s)" % (field[0], field[1].get_name()))

    return "%s dict: contains %s" % (model_name_u(model.get_name()), ", ".join(fields))


def get_gateway_api_code(models):
    """ Get code for gateway_api.py """
    code = []

    for model in models:
        model_name = model.get_name()
        python_name = model_name_u(model_name)

        if model.has_id():
            code.append('def get_%s(self, id, fields=None):' % python_name)
            code.append('    """')
            code.append('    Get a specific %s defined by its id.' % python_name)
            code.append('')
            code.append('    :param id: The id of the %s' % python_name)
            code.append('    :type id: Id')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: List of strings')
            code.append('    :returns: %s' % model_dict_descr_read(model))
            code.append('    """')
            code.append('    return self.__eeprom_controller.read(%s, id, fields).to_dict()' %
                        model_name)
            code.append('')
            code.append('def get_%ss(self, fields=None):' % python_name)
            code.append('    """')
            code.append('    Get all %ss.' % python_name)
            code.append('')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: List of strings')
            code.append('    :returns: list of %s' % model_dict_descr_read(model))
            code.append('    """')
            code.append('    return [ o.to_dict() for o in '
                        'self.__eeprom_controller.read_all(%s, fields) ]' % model_name)
            code.append('')
            code.append('def set_%s(self, config):' % python_name)
            code.append('    """')
            code.append('    Set one %s.' % python_name)
            code.append('')
            code.append('    :param config: The %s to set' % python_name)
            code.append('    :type config: %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.__eeprom_controller.write(%s.from_dict(config))' % model_name)
            code.append('')
            code.append('def set_%ss(self, config):' % python_name)
            code.append('    """')
            code.append('    Set multiple %ss.' % python_name)
            code.append('')
            code.append('    :param config: The list of %ss to set' % python_name)
            code.append('    :type config: list of %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.__eeprom_controller.write_batch('
                        '[ %s.from_dict(o) for o in config ] )' % model_name)
            code.append('')
        else:
            code.append('def get_%s(self, fields=None):' % python_name)
            code.append('    """')
            code.append('    Get the %s.' % python_name)
            code.append('')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: List of strings')
            code.append('    :returns: %s' % model_dict_descr_read(model))
            code.append('    """')
            code.append('    return self.__eeprom_controller.read(%s, fields).to_dict()' %
                        model_name)
            code.append('')
            code.append('def set_%s(self, config):' % python_name)
            code.append('    """')
            code.append('    Set the %s.' % python_name)
            code.append('')
            code.append('    :param config: The %s to set' % python_name)
            code.append('    :type config: %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.__eeprom_controller.write(%s.from_dict(config))' % model_name)
            code.append('')

    return code


def get_webservice_code(models):
    """ Create code for webservice.py. """
    code = []

    for model in models:
        model_name = model.get_name()
        python_name = model_name_u(model_name)

        if model.has_id():
            code.append('@cherrypy.expose')
            code.append('def get_%s(self, token, id, fields=None):' % (python_name))
            code.append('    """')
            code.append('    Get a specific %s defined by its id.' % python_name)
            code.append('')
            code.append('    :param id: The id of the %s' % python_name)
            code.append('    :type id: Id')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: Json encoded list of strings')
            code.append("    :returns: 'config': %s" % model_dict_descr_read(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    fields = None if fields is None else json.loads(fields)')
            code.append('    return self.__success(config='
                        'self.__gateway_api.get_%s(int(id), fields))' % python_name)
            code.append('')
            code.append('@cherrypy.expose')
            code.append('def get_%ss(self, token, fields=None):' % python_name)
            code.append('    """')
            code.append('    Get all %ss.' % python_name)
            code.append('')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: Json encoded list of strings')
            code.append("    :returns: 'config': list of %s" % model_dict_descr_read(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    fields = None if fields is None else json.loads(fields)')
            code.append('    return self.__success(config=self.__gateway_api.get_%ss(fields))' %
                        python_name)
            code.append('')
            code.append('@cherrypy.expose')
            code.append('def set_%s(self, token, config):' % python_name)
            code.append('    """')
            code.append('    Set one %s.' % python_name)
            code.append('')
            code.append('    :param config: The %s to set' % python_name)
            code.append('    :type config: %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    self.__gateway_api.set_%s(json.loads(config))' % python_name)
            code.append('    return self.__success()')
            code.append('')
            code.append('@cherrypy.expose')
            code.append('def set_%ss(self, token, config):' % python_name)
            code.append('    """')
            code.append('    Set multiple %ss.' % python_name)
            code.append('')
            code.append('    :param config: The list of %ss to set' % python_name)
            code.append('    :type config: list of %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    self.__gateway_api.set_%ss(json.loads(config))' % python_name)
            code.append('    return self.__success()')
            code.append('')
        else:
            code.append('@cherrypy.expose')
            code.append('def get_%s(self, token, fields=None):' % python_name)
            code.append('    """')
            code.append('    Get the %s.' % python_name)
            code.append('')
            code.append('    :param fields: The field of the %s to get. (None gets all fields)' %
                        python_name)
            code.append('    :type fields: Json encoded list of strings')
            code.append("    :returns: 'config': %s" % model_dict_descr_read(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    fields = None if fields is None else json.loads(fields)')
            code.append('    return self.__success(config=self.__gateway_api.get_%s(fields))' %
                        python_name)
            code.append('')
            code.append('@cherrypy.expose')
            code.append('def set_%s(self, token, config):' % python_name)
            code.append('    """')
            code.append('    Set the %s.' % python_name)
            code.append('')
            code.append('    :param config: The %s to set' % python_name)
            code.append('    :type config: %s' % model_dict_descr_write(model))
            code.append('    """')
            code.append('    self.check_token(token)')
            code.append('    self.__gateway_api.set_%s(json.loads(config))' % python_name)
            code.append('    return self.__success()')
            code.append('')

    return code


def main():
    """ The main function. """
    models = [OutputConfiguration, InputConfiguration, ThermostatConfiguration,
              SensorConfiguration, PumpGroupConfiguration, GroupActionConfiguration,
              ScheduledActionConfiguration, PulseCounterConfiguration, StartupActionConfiguration,
              DimmerConfiguration, GlobalThermostatConfiguration]

    print "-----------------------------------------"
    print "gateway_api code (gateway/gateway_api.py)"
    print "-----------------------------------------"
    print "\n".join(get_gateway_api_code(models))
    sys.stdin.readline()
    print ""
    print "---------------------------------------"
    print "webservice code (gateway/webservice.py)"
    print "---------------------------------------"
    print "\n".join(get_webservice_code(models))
    print ""


if __name__ == "__main__":
    main()
