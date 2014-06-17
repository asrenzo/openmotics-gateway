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
The scheduling module contains the SchedulingController, this controller is used for scheduled
actions.

Created on May 22, 2013

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import sqlite3
import os

from time import time
from threading import Thread
from Queue import PriorityQueue, Queue, Empty

REFRESH = "Please SchedulingController, would you refresh the action queue ?"

class SchedulingController(object):
    """ The SchedulingController keeps track of the actions that are scheduled and calls a callback
    when the actions has to be executed. The SchedulingController handles actions as String, it is
    the callers responsibility to create a string representation of the action. """

    def __init__(self, db_filename, callback, action_timeout=60):
        new_database = not os.path.exists(db_filename)
        self.__connection = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False, isolation_level=None)
        self.__cursor = self.__connection.cursor()
        if new_database:
            self.__create_tables()

        self.__callback = callback
        self.__action_timeout = action_timeout
        self.__stop = False

        self.__input_queue = Queue()
        self.__action_queue = PriorityQueue()

        for action in self.__read_actions():
            self.__action_queue.put(action)

        self.__thread = Thread(target=self.__run, name="SchedulingController thread")
        self.__thread.daemon = True

    def __create_tables(self):
        """ Create the Scheduled actions table. """
        self.__cursor.execute("CREATE TABLE actions (id INTEGER PRIMARY KEY, description TEXT, "
                              "action TEXT, timestamp INTEGER);")

    def __read_actions(self):
        """ Read the actions from the table. """
        ret = []
        for row in self.__cursor.execute("SELECT timestamp, id, description, action FROM actions;"):
            ret.append((row[0], row[1], row[2], row[3]))
        return ret

    def __create_action(self, timestamp, description, action):
        """ Create an action with a given timestamp in the database.
        Returns the id of the action in the datbase.
        """
        self.__cursor.execute("INSERT INTO actions (timestamp, description, action) VALUES (?,?,?)",
                              (timestamp, description, action))
        return (timestamp, self.__cursor.lastrowid, description, action)

    def __remove_action_from_db(self, id):
        """ Remove an action from the database. """
        self.__cursor.execute("DELETE FROM actions WHERE id = ?;", (id,))

    def __execute_action(self, id, description, action):
        """ Execute a scheduled action, delete the action from the database and execute it. """
        LOGGER.info("Executing scheduled action '%s'", description)
        self.__remove_action_from_db(id)

        def run_callback():
            """ Run the callback. """
            try:
                self.__callback(action)
            except:
                LOGGER.exception("Exception while executing scheduled action '%s'", description)

        callback_thread = Thread(target=run_callback)
        callback_thread.daemon = True
        callback_thread.start()

        callback_thread.join(self.__action_timeout)
        if callback_thread.isAlive():
            LOGGER.error("Scheduled action '%s' is still executing after %d sec",
                         description, self.__action_timeout)

    def start(self):
        """ Start the background thread. """
        self.__thread.start()

    def stop(self):
        """ Stop the SchedulingController. """
        self.__stop = True
        self.__input_queue.put(None)
        self.__thread.join()

    def __run(self):
        """ Code for the background thread. """
        while not self.__stop:
            # Wait on the input_queue, take actions from the action_queue when scheduled.
            timeout = None

            while self.__action_queue.qsize() > 0:
                element = self.__action_queue.get()
                (timestamp, id, description, action) = element

                if timestamp <= time():
                    self.__execute_action(id, description, action)
                else:
                    timeout = timestamp - time()
                    self.__action_queue.put(element)
                    break

            try:
                value = self.__input_queue.get(True, timeout)
                if value == None:       # Stop signal !
                    continue
                elif value == REFRESH:  # Refresh the action queue
                    self.__action_queue = PriorityQueue()
                    for action in self.__read_actions():
                        self.__action_queue.put(action)
                else:                   # Got a new action
                    (timestamp, description, action) = value
                    self.__action_queue.put(self.__create_action(timestamp, description, action))
            except Empty:
                pass                    # Timeout - do the loop

    def schedule_action(self, timestamp, description, action):
        """ Schedule a new action, that should be executed at a given timestamp. """
        self.__input_queue.put((timestamp, description, action))

    def list_scheduled_actions(self):
        """ Get a list of all scheduled actions.
        :returns: a list of dictionaries with keys (id, timestamp, description, action)
        """
        actions = self.__read_actions()
        ret = []
        for action in actions:
            ret.append({'timestamp' : action[0], 'id' : action[1],
                        'description' : action[2], 'action' : action[3]})
        return ret

    def remove_scheduled_action(self, id):
        """ Remove a scheduled action, when the id of the scheduled action is provided. """
        self.__remove_action_from_db(id)
        self.__input_queue.put(REFRESH)

    def close(self):
        """ Commit the changes and close the database connection. """
        self.__connection.commit()
        self.__connection.close()
