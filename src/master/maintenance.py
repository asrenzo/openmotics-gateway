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
The maintenance module contains the MaintenanceService class.

Created on Sep 22, 2012

@author: fryckbos
'''
import logging
LOGGER = logging.getLogger("openmotics")

import threading
import traceback
import socket
import select
from OpenSSL import SSL

from master_communicator import InMaintenanceModeException

class MaintenanceService(object):
    """ The maintenance service accepts tcp connections. If a connection is accepted it
    grabs the serial port, sets the gateway mode to CLI and forwards input and output
    over the tcp connection.
    """

    def __init__(self, gateway_api, privatekey_filename, certificate_filename):
        """ Construct a MaintenanceServer.

        :param gateway_api: the communication with the master.
        :param privatekey_filename: the filename of the private key for the SSL connection.
        :param certificate_filename: the filename of the certificate for the SSL connection.
        """
        self.__gateway_api = gateway_api
        self.__context = SSL.Context(SSL.SSLv23_METHOD)
        self.__context.use_privatekey_file(privatekey_filename)
        self.__context.use_certificate_file(certificate_filename)

    def start_in_thread(self, port, connection_timeout=60):
        """ Start the maintenance service in a new thread. The maintenance service only accepts
        one connection. If this connection is not established within the connection_timeout, the
        server socket is closed.

        :param port: the port for the SSL socket.
        :param connection_timeout: timeout for the server socket.
        """
        thread = threading.Thread(target=self.start, args=(port, connection_timeout))
        thread.setName("Maintenance thread")
        thread.daemon = True
        thread.start()

    def start(self, port, connection_timeout):
        """ Run the maintenance service, accepts a connection. Starts a serial
        redirector when a connection is accepted.
        """
        LOGGER.info("Starting maintenance socket on port " + str(port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(connection_timeout)
        sock = SSL.Connection(self.__context, sock)
        sock.bind(('', port))
        sock.listen(1)

        try:
            LOGGER.info("Waiting for maintenance connection.")
            connection, addr = sock.accept()
            self.handle_connection(connection, str(addr))
            LOGGER.info("Maintenance session ended, closing maintenance socket")
            sock.close()
        except socket.timeout:
            LOGGER.info("Maintenance socket timed out, closing.")
            sock.close()
        except Exception:
            LOGGER.error("Error in maintenance service: %s\n", traceback.format_exc())
            sock.close()

    def handle_connection(self, connection, addr):
        """ Handles one incoming connection.
        """
        LOGGER.info("Maintenance connection from %s\n", addr)
        connection.settimeout(1)
        try:
            connection.sendall("Starting maintenance mode, "
                               "waiting for other actions to complete ...\n")
            self.__gateway_api.start_maintenance_mode()
            LOGGER.info("Maintenance connection got lock\n")

            serial_redirector = SerialRedirector(self.__gateway_api, connection)
            serial_redirector.run()
        except InMaintenanceModeException:
            connection.sendall("Maintenance mode already started. Closing connection.")
        finally:
            LOGGER.info("Maintenance connection closed")
            self.__gateway_api.stop_maintenance_mode()
            connection.close()


class SerialRedirector(object):
    """ Takes an acquired serial connection and a socket an redirects
    the serial traffic over the socket.
    """

    def __init__(self, gateway_api, connection):
        self.__gateway_api = gateway_api
        self.__connection = connection
        self.__reader_thread = None
        self.__stopped = False

    def run(self):
        """ Run the serial redirector, spins off a reader thread and uses
        the current thread for writing
        """
        self.__reader_thread = threading.Thread(target=self.reader)
        self.__reader_thread.setName("Maintenance reader thread")
        self.__reader_thread.start()
        self.writer()

    def stop(self):
        """ Stop the serial redirector. """
        self.__stopped = True

    def is_running(self):
        """ Check whether the SerialRedirector is still running. """
        return not self.__stopped

    def writer(self):
        """ Reads from the socket and writes to the serial port. """
        while not self.__stopped:
            try:
                try:
                    data = self.__connection.recv(1024)
                except SSL.SysCallError as exception:
                    if exception[0] == 11: ## temporarily unavailable
                        continue
                    else:
                        raise
                except SSL.WantReadError:
                    select.select([self.__connection], [], [], 1.0)
                else:
                    if not data:
                        LOGGER.info("Stopping maintenance mode due to no data.")
                    if data.startswith("exit"):
                        LOGGER.info("Stopping maintenance mode due to exit.")
                        break
                    self.__gateway_api.send_maintenance_data(data)
            except:
                LOGGER.error("Exception in maintenance mode: %s\n", traceback.format_exc())
                break

        self.__stopped = True
        self.__reader_thread.join()


    def reader(self):
        """ Reads from the serial port and writes to the socket. """
        while not self.__stopped:
            try:
                data = self.__gateway_api.get_maintenance_data()
                if data:
                    self.__connection.sendall(data)
            except:
                LOGGER.error("Exception in maintenance mode: %s\n", traceback.format_exc())
                break

        self.__stopped = True
