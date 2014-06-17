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

""" MasterApi enables communication with master over serial port.
Provides a function for each API call.

Created on Sep 9, 2012

@author: fryckbos
"""
import math

import master_api
from serial_utils import printable

class MasterCommandSpec(object):
    """ The input command to the master looks like this:
    'STR' [Action (2 bytes)] [cid] [fields] '\r\n'
    The first 6 and last 2 bytes are fixed, the rest should be in fields.

    The output looks like this:
    [Action (2 bytes)] [cid] [fields]
    The total length depends on the action.
    """
    def __init__(self, action, input_fields, output_fields):
        """ Create a MasterCommandSpec.

        :param action: name of the action as described in the Master api.
        :type action: 2-byte string
        :param input_fields: Fields in the input to the master
        :type input_fields: array of :class`Field`
        :param output_fields: Fields in the output from the master
        :type output_fields: array of :class`Field`
        """
        self.action = action
        self.input_fields = input_fields
        self.output_fields = output_fields

    def create_input(self, cid, fields=None):
        """ Create an input command for the master using this spec and the provided fields.

        :param cid: communication id
        :type cid: byte
        :param fields: dictionary with values for the fields
        :type fields: dict
        :rtype: string
        """
        if fields is None:
            fields = dict()

        start = "STR" + self.action + chr(cid)
        encoded_fields = ""
        for field in self.input_fields:
            if Field.is_crc(field):
                encoded_fields += self.__calc_crc(encoded_fields)
            else:
                encoded_fields += field.encode(fields.get(field.name))

        return start + encoded_fields + "\r\n"

    def __calc_crc(self, encoded_string):
        """ Calculate the crc of an string. """
        crc = 0
        for byte in encoded_string:
            crc += ord(byte)

        return 'C' + chr(crc / 256) + chr(crc % 256)

    def create_output(self, cid, fields):
        """ Create an output command from the master using this spec and the provided fields.
        Only used for testing !

        :param cid: communication id
        :type cid: byte
        :param fields: dictionary with values for the fields
        :type fields: dict
        :rtype: string
        """
        ret = self.action + chr(cid)
        for field in self.output_fields:
            ret += field.encode(fields.get(field.name))
        return ret

    def consume_output(self, byte_str, partial_result=None):
        """ When the prefix of a command is matched, consume_output is used to fill in the
        output fields. If a part of the fields was already matched, the parial_result should
        be provided. The output of this method indicates how many bytes were consumed, the
        result and if the consumption was done.

        :param byte_str Output from the master
        :type byte_str: string of bytes
        :param partial_result: In case we already have data for this unfinished communication.
        :type partial_result: None if no partial result yet
        :rtype: tuple of (bytes consumed(int), result(Result), done(bool))
        """
        if partial_result == None:
            from_pending = 0
            partial_result = Result()
        else:
            from_pending = len(partial_result.pending_bytes)
            byte_str = partial_result.pending_bytes + byte_str
            partial_result.pending_bytes = ""

        def decode_field(index, byte_str, field, num_bytes):
            """ Decode one field, returns index for the next field if successful,
            returns a tuple with decode information if not successful."""
            if index + num_bytes <= len(byte_str):
                try:
                    decoded = field.decode(byte_str[index:index + num_bytes])
                except NeedMoreBytesException, nmbe:
                    return decode_field(index, byte_str, field, nmbe.bytes_required)
                else:
                    partial_result[field.name] = decoded
                    partial_result.field_index += 1
                    partial_result.pending_bytes = ""
                    index += num_bytes
                    return index
            else:
                partial_result.pending_bytes += byte_str[index:]
                return (len(byte_str) - from_pending, partial_result, False)

        # Found beginning, start decoding
        index = 0
        for field in self.output_fields[partial_result.field_index:]:
            index = decode_field(index, byte_str, field, field.get_min_decode_bytes())
            if type(index) != int:
                # We ran out of bytes
                return index

        partial_result.complete = True
        return (index - from_pending, partial_result, True)

    def output_has_crc(self):
        """ Check if the MasterCommandSpec output contains a crc field. """
        for field in self.output_fields:
            if Field.is_crc(field):
                return True

        return False

    def __eq__(self, other):
        """ Only used for testing, equals by name. """
        return self.action == other.action

class Result(object):
    """ Result of a communication with the master. Can be accessed as a dict,
    contains the output fields specified in the spec."""

    def __init__(self):
        """ Create a new incomplete result. """
        self.complete = False
        self.field_index = 0
        self.fields = {}
        self.pending_bytes = ""

    def __getitem__(self, key):
        """ Implemented so class can be accessed as a dict. """
        return self.fields[key]

    def __setitem__(self, key, value):
        """ Implemented so class can be accessed as a dict. """
        self.fields[key] = value


class Field(object):
    """ Field of a master command has a name, type.
    """
    @staticmethod
    def byte(name):
        """ Create 1-byte field with a certain name.
        The byte type takes an int as input. """
        return Field(name, FieldType(int, 1))

    @staticmethod
    def int(name):
        """ Create 2-byte field with a certain name.
        The byte type takes an int as input. """
        return Field(name, FieldType(int, 2))

    @staticmethod
    def str(name, length):
        """ Create a string field with a certain name and length. """
        return Field(name, FieldType(str, length))

    @staticmethod
    def bytes(name, length):
        """ Create a byte array with a certain name and length. """
        return Field(name, BytesFieldType(length))

    @staticmethod
    def padding(length):
        """ Padding, will be skipped. """
        return Field("padding", PaddingFieldType(length))

    @staticmethod
    def lit(value):
        """ Literal value """
        return Field("literal", LiteralFieldType(value))

    @staticmethod
    def varstr(name, max_data_length):
        """ String of variable length with fixed total length """
        return Field(name, VarStringFieldType(max_data_length))

    @staticmethod
    def svt(name):
        """ System value time """
        return Field(name, SvtFieldType())

    @staticmethod
    def dimmer(name):
        """ Dimmer type (byte in [0, 63] converted to integer in [0, 100]. """
        return Field(name, DimmerFieldType())

    @staticmethod
    def hum(name):
        """ Humidity value. """
        return Field(name, HumidityFieldType())

    @staticmethod
    def crc():
        """ Create a crc field type (3-byte string) """
        return Field.bytes('crc', 3)

    @staticmethod
    def is_crc(field):
        """ Is the field a crc field ? """
        return isinstance(field, Field) and field.name == 'crc' \
                and isinstance(field.field_type, BytesFieldType) and field.field_type.length == 3

    def __init__(self, name, field_type):
        """ Create a MasterComandField.

        :param name: name of the field as described in the Master api.
        :type name: String
        :param field_type: type of the field.
        :type field_type: :class`FieldType`
        """
        self.name = name
        self.field_type = field_type

    def encode(self, field_value):
        """ Generate an encoded field.

        :param field_value: the value of the field.
        :type field_value: type of value depends on type of field.
        """
        return self.field_type.encode(field_value)

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.field_type.get_min_decode_bytes()

    def decode(self, byte_str):
        """ Decode a string of bytes. If there are not enough bytes, a
        :class`MoreBytesRequiredException` will be thrown.

        :param bytes: array of types (string)
        :rtype: a string if done, otherwise the amount of bytes required to decode
        """
        return self.field_type.decode(byte_str)

class NeedMoreBytesException(Exception):
    """ Throw in case a decode requires more bytes then provided. """
    def __init__(self, bytes_required):
        Exception.__init__(self)
        self.bytes_required = bytes_required

class FieldType(object):
    """ Describes the type of a MasterCommandField.
    """
    def __init__(self, python_type, length):
        """ Create a FieldType using a python type. Supports int and str.
        Throws a ValueError if the type is not int or str.

        :param python_type: type of the field
        :type python_type: type
        :param length: length of the encoded field
        :type length: int
        """
        if python_type == int or python_type == str:
            self.python_type = python_type
            self.length = length
        else:
            raise ValueError('Only int and str are supported, got: ' + str(python_type))

    def encode(self, field_value):
        """ Get the encoded value. The field_values type should match the python_type.

        :param field_value: value of the field to encode.
        :type field_value: python_type provided in constructor.
        """
        if self.python_type == int and self.length == 1:
            if field_value < 0 or field_value > 255:
                raise ValueError('Int does not fit in byte: %d' % field_value)
            else:
                return chr(field_value)
        elif self.python_type == int and self.length == 2:
            if field_value < 0 or field_value > 65535:
                raise ValueError('Int does not fit in 2 bytes: %d' % field_value)
            else:
                return str(chr(field_value / 256)) + str(chr(field_value % 256))
        elif self.python_type == str:
            if len(field_value) != self.length:
                raise ValueError('String is not of the correct length: expected %d, got %d' %
                                 (self.length, len(field_value)))
            else:
                return field_value

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def decode(self, byte_str):
        """ Decode the bytes.

        :param bytes: array of types (string)
        """
        if len(byte_str) != self.length:
            raise ValueError('Byte array is not of the correct length: expected %d, got %d' %
                                 (self.length, len(byte_str)))
        else:
            if self.python_type == int and self.length == 1:
                return ord(byte_str[0])
            elif self.python_type == int and self.length == 2:
                return ord(byte_str[0]) * 256 + ord(byte_str[1])
            elif self.python_type == str:
                return byte_str

class PaddingFieldType(object):
    """ Empty field. """
    def __init__(self, length):
        self.length = length

    def encode(self, _):
        """ Encode returns string of \x00 """
        return '\x00' * self.length

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def decode(self, byte_str):
        """ Only checks if byte_str size is correct, returns None """
        if len(byte_str) != self.length:
            raise ValueError('Byte array is not of the correct length: expected %d, got %d' %
                                 (self.length, len(byte_str)))
        else:
            return ""

class BytesFieldType(object):
    """ Type for an array of bytes. """
    def __init__(self, length):
        self.length = length

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.length

    def encode(self, byte_arr):
        """ Generates a string of bytes from the byte array. """
        return ''.join([chr(x) for x in byte_arr])

    def decode(self, byte_str):
        """ Generates an array of bytes. """
        return [ord(x) for x in byte_str]

class LiteralFieldType(object):
    """ Literal string field. """
    def __init__(self, literal):
        self.literal = literal

    def encode(self, _):
        """ Returns the literal """
        return self.literal

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return len(self.literal)

    def decode(self, byte_str):
        """ Checks if byte_str is the literal """
        if byte_str != self.literal:
            raise ValueError('Byte array does not match literal: expected %s, got %s' %
                                 (printable(self.literal), printable(byte_str)))
        else:
            return ""

class SvtFieldType(object):
    """ The System value temperature is one byte. This types encodes and decodes into
    a float (degrees Celsius).
    """
    def __init__(self):
        pass

    def encode(self, field_value):
        """ Encode an instance of the Svt class to a byte. """
        return field_value.get_byte()

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    def decode(self, byte_str):
        """ Decode a svt byte string into a instance of the Svt class. """
        return master_api.Svt.from_byte(byte_str[0])

class HumidityFieldType(object):
    """ The humidity field is one byte. This types encodes and decodes
    into a float (percentage).
    """
    def __init__(self):
        pass

    def encode(self, field_value):
        """ Encode an instance of the Svt class to a byte. """
        return chr(int(field_value * 2) if field_value != 255.0 else 255)

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    def decode(self, byte_str):
        """ Decode a byte string into a float. """
        value = ord(byte_str[0])
        return (value / 2.0) if value != 255 else 255.0

class VarStringFieldType(object):
    """ The VarString uses 1 byte for the length, the total length of the string is fixed.
    Unused bytes are padded with spaces.
    """
    def __init__(self, total_data_length):
        self.total_data_length = total_data_length

    def encode(self, field_value):
        """ Encode a string. """
        if len(field_value) > self.total_data_length:
            raise ValueError("Cannot handle more than %d bytes, got %d",
                             self.total_data_length, len(field_value))
        else:
            out = chr(len(field_value))
            out += field_value
            out += " " * (self.total_data_length - len(field_value))
            return out

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return self.total_data_length + 1

    def decode(self, byte_str):
        """ Decode the data into a string (without padding) """
        length = ord(byte_str[0])
        return byte_str[1:1+length]


class DimmerFieldType(object):
    """ The dimmer value is a byte in [0, 63], this is converted to an integer in [0, 100] to
    provide a consistent interface with the set dimmer method. The transfer function is not
    completely linear: [0, 54] maps to [0, 90] and [54, 63] maps to [92, 100].
    """
    def __init__(self):
        pass

    def encode(self, field_value):
        """ Encode a dimmer value. """
        if field_value <= 90:
            return chr(int(math.ceil(field_value * 6.0 / 10.0)))
        else:
            return chr(int(53 + field_value - 90))

    def decode(self, byte_str):
        """ Decode a byte [0, 63] to an integer [0, 100]. """
        dimmer_value = ord(byte_str[0])
        if dimmer_value <= 54:
            return int(dimmer_value * 10.0 / 6.0)
        else:
            return int(90 + dimmer_value - 53)

    def get_min_decode_bytes(self):
        """ The dimmer type is always 1 byte. """
        return 1

class OutputFieldType(object):
    """ Field type for OL. """
    def __init__(self):
        pass

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    def decode(self, byte_str):
        """ Decode a byte string. """
        bytes_required = 1 + (ord(byte_str[0]) * 2)

        if len(byte_str) < bytes_required:
            raise NeedMoreBytesException(bytes_required)
        elif len(byte_str) > bytes_required:
            raise ValueError("Got more bytes than required: expected %d, got %d",
                             bytes_required, len(byte_str))
        else:
            dimmer_field_type = DimmerFieldType()
            out = []
            for i in range(ord(byte_str[0])):
                id = ord(byte_str[1 + i*2])
                dimmer = dimmer_field_type.decode(byte_str[1 + i*2 + 1:1 + i*2 + 2])
                out.append((id, dimmer))
            return out

class ErrorListFieldType(object):
    """ Field type for el. """
    def __init__(self):
        pass

    def get_min_decode_bytes(self):
        """ Get the minimal amount of bytes required to start decoding. """
        return 1

    def encode(self, field_value):
        """ Encode to byte string. """
        bytes = ""
        bytes += chr(len(field_value))
        for field in field_value:
            bytes += "%s%s%s%s" % (field[0][0],
                                   chr(int(field[0][1:])),
                                   chr(field[1] / 256),
                                   chr(field[1] % 256))
        return bytes

    def decode(self, byte_str):
        """ Decode a byte string. """
        nr_modules = ord(byte_str[0])
        bytes_required = 1 + (nr_modules * 4)

        if len(byte_str) < bytes_required:
            raise NeedMoreBytesException(bytes_required)
        elif len(byte_str) > bytes_required:
            raise ValueError("Got more bytes than required: expected %d, got %d",
                             bytes_required, len(byte_str))
        else:
            out = []
            for i in range(nr_modules):
                id = "%s%d" % (byte_str[i*4 + 1], ord(byte_str[i*4 + 2]))
                nr_errors = ord(byte_str[i*4 + 3]) * 256 + ord(byte_str[i*4 + 4])

                out.append((id, nr_errors))

            return out
