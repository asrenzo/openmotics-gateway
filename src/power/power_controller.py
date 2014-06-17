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
The power controller module contains the PowerController class, which keeps track of the registered
power modules and their address.
'''

import sqlite3
import os.path

class PowerController(object):
    """ The PowerController keeps track of the registered power modules. """

    def __init__(self, db_filename):
        """ Constructor a new PowerController.

        :param db_filename: filename of the sqlite database.
        """
        new_database = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        if new_database:
            self.__create_tables()

    def __create_tables(self):
        """ Create the power tables. """
        self.__cursor.execute("CREATE TABLE power_modules (id INTEGER PRIMARY KEY, "
                              "name TEXT default '', address INTEGER, "
                              "input0 TEXT default '', input1 TEXT default '', "
                              "input2 TEXT default '', input3 TEXT default '', "
                              "input4 TEXT default '', input5 TEXT default '', "
                              "input6 TEXT default '', input7 TEXT default '', "
                              "sensor0 INT default 0, sensor1 INT default 0, "
                              "sensor2 INT default 0, sensor3 INT default 0, "
                              "sensor4 INT default 0, sensor5 INT default 0, "
                              "sensor6 INT default 0, sensor7 INT default 0, "
                              "times0 TEXT, times1 TEXT, times2 TEXT, times3 TEXT, "
                              "times4 TEXT, times5 TEXT, times6 TEXT, times7 TEXT );")

    def get_power_modules(self):
        """ Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict containing 'id', 'name', 'address', 'input0', 'input1', 'input2',
        'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', 'sensor2',
        'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', 'times2',
        'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        power_modules = {}
        for row in self.__cursor.execute("SELECT id, name, address, input0, input1, input2, "
                                         "input3, input4, input5, input6, input7, sensor0, "
                                         "sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, "
                                         "sensor7, times0, times1, times2, times3, times4, "
                                         "times5, times6, times7 FROM power_modules;"):
            power_modules[row[0]] = {'id': row[0], 'name': row[1], 'address': row[2],
                                     'input0': row[3], 'input1': row[4], 'input2': row[5],
                                     'input3':row[6], 'input4':row[7], 'input5': row[8],
                                     'input6':row[9], 'input7':row[10],
                                     'sensor0': row[11], 'sensor1': row[12], 'sensor2': row[13],
                                     'sensor3':row[14], 'sensor4':row[15], 'sensor5': row[16],
                                     'sensor6':row[17], 'sensor7':row[18], 'times0':row[19],
                                     'times1':row[20], 'times2':row[21], 'times3':row[22],
                                     'times4':row[23], 'times5':row[24], 'times6':row[25],
                                     'times7':row[26]}
        return power_modules

    def get_address(self, id):
        """ Get the address of a module when the module id is provided. """
        for row in self.__cursor.execute("SELECT address FROM power_modules WHERE id=?;",
                                         (id,)):
            return row[0]

    def module_exists(self, address):
        """ Check if a module with a certain address exists. """
        for row in self.__cursor.execute("SELECT count(id) FROM power_modules WHERE address=?;",
                                         (address,)):
            return row[0] > 0

    def update_power_module(self, module):
        """ Update the name and names of the inputs of the power module.

        :param module: dicts with keys: 'id', 'name', 'input0', 'input1', 'input2', \
        'input3', 'input4', 'input5', 'input6', 'input7', 'sensor0', 'sensor1', 'sensor2', \
        'sensor3', 'sensor4', 'sensor5', 'sensor6', 'sensor7', 'times0', 'times1', 'times2', \
        'times3', 'times4', 'times5', 'times6', 'times7'.
        """
        self.__cursor.execute("UPDATE power_modules SET "
                              "name=?, input0=?, input1=?, input2=?, input3=?, "
                              "input4=?, input5=?, input6=?, input7=?, sensor0=?, sensor1=?, "
                              "sensor2=?, sensor3=?, sensor4=?, sensor5=?, sensor6=?, sensor7=?, "
                              "times0=?, times1=?, times2=?, times3=?, times4=?, times5=?, "
                              "times6=?, times7=? WHERE id=?;",
                              (module['name'], module['input0'], module['input1'],
                               module['input2'], module['input3'], module['input4'],
                               module['input5'], module['input6'], module['input7'],
                               module['sensor0'], module['sensor1'], module['sensor2'],
                               module['sensor3'], module['sensor4'], module['sensor5'],
                               module['sensor6'], module['sensor7'], module['times0'],
                               module['times1'], module['times2'], module['times3'],
                               module['times4'], module['times5'], module['times6'],
                               module['times7'], module['id']))
        self.__connection.commit()

    def register_power_module(self, address):
        """ Register a new power module using an address. """
        self.__cursor.execute("INSERT INTO power_modules(address) VALUES (?);", (address,))
        self.__connection.commit()

    def readdress_power_module(self, old_address, new_address):
        """ Change the address of a power module. """
        self.__cursor.execute("UPDATE power_modules SET address=? WHERE address=?;",
                              (new_address, old_address))
        self.__connection.commit()

    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        for row in self.__cursor.execute("SELECT address FROM power_modules;"):
            max_address = max(max_address, row[0])
        return max_address + 1 if max_address < 255 else 1

    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
