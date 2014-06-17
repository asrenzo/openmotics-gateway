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

""" Contains PowerCommandClass that describes a command to the power modules. The PowerCommand
class is used to create the power_api.

@author: fryckbos
"""

import struct

CRC_TABLE = [0, 49, 98, 83, 196, 245, 166, 151, 185, 136, 219, 234, 125, 76, 31, 46, 67, 114, 33,
             16, 135, 182, 229, 212, 250, 203, 152, 169, 62, 15, 92, 109, 134, 183, 228, 213, 66,
             115, 32, 17, 63, 14, 93, 108, 251, 202, 153, 168, 197, 244, 167, 150, 1, 48, 99, 82,
             124, 77, 30, 47, 184, 137, 218, 235, 61, 12, 95, 110, 249, 200, 155, 170, 132, 181,
             230, 215, 64, 113, 34, 19, 126, 79, 28, 45, 186, 139, 216, 233, 199, 246, 165, 148,
             3, 50, 97, 80, 187, 138, 217, 232, 127, 78, 29, 44, 2, 51, 96, 81, 198, 247, 164, 149,
             248, 201, 154, 171, 60, 13, 94, 111, 65, 112, 35, 18, 133, 180, 231, 214, 122, 75, 24,
             41, 190, 143, 220, 237, 195, 242, 161, 144, 7, 54, 101, 84, 57, 8, 91, 106, 253, 204,
             159, 174, 128, 177, 226, 211, 68, 117, 38, 23, 252, 205, 158, 175, 56, 9, 90, 107, 69,
             116, 39, 22, 129, 176, 227, 210, 191, 142, 221, 236, 123, 74, 25, 40, 6, 55, 100, 85,
             194, 243, 160, 145, 71, 118, 37, 20, 131, 178, 225, 208, 254, 207, 156, 173, 58, 11,
             88, 105, 4, 53, 102, 87, 192, 241, 162, 147, 189, 140, 223, 238, 121, 72, 27, 42, 193,
             240, 163, 146, 5, 52, 103, 86, 120, 73, 26, 43, 188, 141, 222, 239, 130, 179, 224, 209,
             70, 119, 36, 21, 59, 10, 89, 104, 255, 206, 157, 172]

def crc7(to_send):
    """ Calculate the crc7 checksum of a string.
    :param to_send: input string
    :rtype: integer
    """
    ret = 0
    for part in to_send:
        ret = CRC_TABLE[ret ^ ord(part)]
    return ret


class PowerCommand(object):
    """ A PowerCommand is an command that can be send to a Power Module over RS485. The commands
    look like this: 'STR' 'E' Address CID Mode(G/S) Type LEN Data CRC7 '\r\n'.
    """

    def __init__(self, mode, type, input_format, output_format):
        """ Create PowerCommand using the fixed fields of the input command and the format of the
        command returned by the power module.

        :param mode: 1 character, S or G
        :param type: 3 byte string, type of the command
        :param input_format: the format of the data in the command
        :param output_format: the format of the data returned by the power module
        """
        self.mode = mode
        self.type = type
        self.input_format = input_format
        self.output_format = output_format

    def create_input(self, address, cid, *data):
        """ Create an input string for the power module using this command and the provided fields.

        :param address: 1 byte, the address of the module
        :param cid: 1 byte, communication id
        :param data: data to send to the power module
        """
        data = struct.pack(self.input_format, *data)

        command = "E" + chr(address) + chr(cid) + str(self.mode) + str(self.type)
        command += chr(len(data)) + str(data)
        return "STR" + command + chr(crc7(command)) + "\r\n"

    def create_output(self, address, cid, *data):
        """ Create an output command from the power module using this command and the provided
        fields. --- Only used for testing !

        :param address: 1 byte, the address of the module
        :param cid: dictionary with values for the fields
        :type fields: dict
        :rtype: string
        """
        data = struct.pack(self.output_format, *data)
        command = "E" + chr(address) + chr(cid) + str(self.mode) + str(self.type)
        command += chr(len(data)) + str(data)
        return "RTR" + command + chr(crc7(command)) + "\r\n"

    def check_header(self, header, address, cid):
        """ Check if the header matches the command, when an address and cid is provided. """
        return header[:-1] == "E" + chr(address) + chr(cid) + str(self.mode) + str(self.type)

    def check_header_partial(self, header):
        """ Check if the header matches the command, does not check address and cid. """
        return header[3:-1] == self.mode + self.type

    def read_output(self, data):
        """ Read the output for a command from the serial port.

        :param cid: 1 byte, communication id
        :param serial: serial port interface (instance of pyserial.Serial)
        """
        return struct.unpack(self.output_format, data)
