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

"""
Tests for MasterCommand module.

Created on Sep 9, 2012

@author: fryckbos
"""
import unittest

import master.master_api as master_api
from master.master_command import MasterCommandSpec, Field, OutputFieldType, DimmerFieldType, \
                                  ErrorListFieldType

class MasterCommandSpecTest(unittest.TestCase):
    """ Tests for :class`MasterCommandSpec` """

    def test_encode_byte_field(self):
        """ Test for Field.byte.encode """
        self.assertEquals('\x00', Field.byte("test").encode(0))
        self.assertEquals('\x01', Field.byte("test").encode(1))
        self.assertEquals('\xFF', Field.byte("test").encode(255))

        try:
            Field.byte("test").encode(-1)
            self.assertTrue(False)
        except ValueError:
            pass

        try:
            Field.byte("test").encode(1024)
            self.assertTrue(False)
        except ValueError:
            pass

    def test_decode_byte_field(self):
        """ Test for Field.byte.decode """
        self.assertEquals(0, Field.byte("test").decode('\x00'))
        self.assertEquals(1, Field.byte("test").decode('\x01'))
        self.assertEquals(255, Field.byte("test").decode('\xFF'))

        try:
            Field.byte("test").decode("ab")
            self.assertTrue(False)
        except ValueError:
            pass

    def test_encode_int_field(self):
        """ Test for Field.int.encode """
        self.assertEquals('\x00\x00', Field.int("test").encode(0))
        self.assertEquals('\x00\x01', Field.int("test").encode(1))
        self.assertEquals('\x01\x11', Field.int("test").encode(1*256 + 17))
        self.assertEquals('\xFF\xFF', Field.int("test").encode(255*256 + 255))

        try:
            Field.int("test").encode(-1)
            self.assertTrue(False)
        except ValueError:
            pass

        try:
            Field.int("test").encode(102400)
            self.assertTrue(False)
        except ValueError:
            pass

    def test_decode_int_field(self):
        """ Test for Field.int.decode """
        self.assertEquals(0, Field.int("test").decode('\x00\x00'))
        self.assertEquals(1, Field.int("test").decode('\x00\x01'))
        self.assertEquals(1*256 + 17, Field.int("test").decode('\x01\x11'))
        self.assertEquals(255*256 + 255, Field.int("test").decode('\xFF\xFF'))

        try:
            Field.int("test").decode("123")
            self.assertTrue(False)
        except ValueError:
            pass


    def test_encode_str_field(self):
        """ Test for Field.str.encode """
        self.assertEquals('', Field.str("test", 0).encode(''))
        self.assertEquals('hello', Field.str("test", 5).encode('hello'))
        self.assertEquals('worlds', Field.str("test", 6).encode('worlds'))

        try:
            Field.str("test", 10).encode('nope')
            self.assertTrue(False)
        except ValueError:
            pass

    def test_decode_str_field(self):
        """ Test for Field.str.decode """
        self.assertEquals('hello', Field.str("test", 5).decode('hello'))
        self.assertEquals('', Field.str("test", 0).decode(''))

        try:
            Field.str("test", 2).decode('nope')
            self.assertTrue(False)
        except ValueError:
            pass

    def test_encode_padding_field(self):
        """ Test for Field.padding.encode """
        self.assertEquals('', Field.padding(0).encode(None))
        self.assertEquals('\x00\x00', Field.padding(2).encode(None))

    def test_decode_padding_field(self):
        """ Test for Field.padding.decode """
        self.assertEquals('', Field.padding(1).decode('\x00'))

        try:
            Field.padding(1).decode('\x00\x00')
            self.assertTrue(False)
        except ValueError:
            pass

    def test_encode_var_string(self):
        """ Test for VarStringFieldType.encode """
        self.assertEquals('\x00' + " " * 10, Field.varstr("bankdata", 10).encode(''))
        self.assertEquals('\x05hello' + " " * 5, Field.varstr("bankdata", 10).encode('hello'))
        self.assertEquals('\x0Ahelloworld', Field.varstr("bankdata", 10).encode('helloworld'))

        try:
            Field.varstr("bankdata", 2).encode('toolarggge')
            self.assertTrue(False)
        except ValueError:
            pass

    def test_svt(self):
        """ Test for SvtFieldType.encode and SvtFieldType.decode """
        svt_field_type = Field.svt("test")
        self.assertEquals('\x42', svt_field_type.encode(master_api.Svt.temp(1.0)))
        self.assertEquals(64.0, svt_field_type.decode(svt_field_type.encode(
                                                    master_api.Svt.temp(64.0))).get_temperature())

    def test_dimmer(self):
        """ Test for DimmerFieldType.encode and DimmerFieldType.decode """
        dimmer_type = DimmerFieldType()
        for value in range(0, 64):
            val = chr(value)
            self.assertEquals(dimmer_type.encode(dimmer_type.decode(val)), val)

    def test_output_wiht_crc(self):
        """ Test crc and is_crc functions. """
        field = Field.crc()

        self.assertEquals('crc', field.name)
        self.assertTrue(Field.is_crc(field))

        field = Field.padding(1)
        self.assertFalse(Field.is_crc(field))

    def test_create_input(self):
        """ Test for MasterCommandSpec.create_input """
        basic_action = MasterCommandSpec("BA",
                    [Field.byte("actionType"), Field.byte("actionNumber"), Field.padding(11)], [])
        ba_input = basic_action.create_input(1, {"actionType": 2, "actionNumber": 4})

        self.assertEquals(21, len(ba_input))
        self.assertEquals("STRBA\x01\x02\x04" + ("\x00" * 11) + "\r\n", ba_input)

    def test_input_with_crc(self):
        """ Test encoding with crc. """
        spec = MasterCommandSpec("TE",
                    [Field.byte("one"), Field.byte("two"), Field.crc()], [])
        spec_input = spec.create_input(1, {"one": 255, "two": 128})

        self.assertEquals(13, len(spec_input))
        self.assertEquals("STRTE\x01\xff\x80C\x01\x7f\r\n", spec_input)

    def test_consume_output(self):
        """ Test for MasterCommandSpec.consume_output """
        basic_action = MasterCommandSpec("BA", [],
                                [Field.str("response", 2), Field.padding(11), Field.lit("\r\n")])

        # Simple case, full string without offset at once
        (bytes_consumed, result, done) = \
            basic_action.consume_output("OK" + ('\x00' * 11) + '\r\n', None)

        self.assertEquals((15, True), (bytes_consumed, done))
        self.assertEquals("OK", result["response"])

        # Full string with extra padding in the back
        (bytes_consumed, result, done) = \
            basic_action.consume_output("OK" + ('\x00' * 11) + '\r\nSome\x04Junk', None)

        self.assertEquals((15, True), (bytes_consumed, done))
        self.assertEquals("OK", result["response"])

        # String in 2 pieces
        (bytes_consumed, result, done) = \
            basic_action.consume_output("OK" + ('\x00' * 5), None)

        self.assertEquals((7, False), (bytes_consumed, done))
        self.assertEquals('\x00' * 5, result.pending_bytes)

        (bytes_consumed, result, done) = \
            basic_action.consume_output(('\x00' * 6) + '\r\n', result)

        self.assertEquals((8, True), (bytes_consumed, done))
        self.assertEquals("OK", result["response"])

        # String in 2 pieces with extra padding in back
        (bytes_consumed, result, done) = \
            basic_action.consume_output("OK" + ('\x00' * 5), None)

        self.assertEquals((7, False), (bytes_consumed, done))
        self.assertEquals('\x00' * 5, result.pending_bytes)

        (bytes_consumed, result, done) = \
            basic_action.consume_output(('\x00' * 6) + '\r\nWorld', result)

        self.assertEquals((8, True), (bytes_consumed, done))
        self.assertEquals("OK", result["response"])

        # String in 3 pieces
        (bytes_consumed, result, done) = \
            basic_action.consume_output("OK" + ('\x00' * 5), None)

        self.assertEquals((7, False), (bytes_consumed, done))
        self.assertEquals('\x00' * 5, result.pending_bytes)

        (bytes_consumed, result, done) = \
            basic_action.consume_output(('\x00' * 3), result)

        self.assertEquals((3, False), (bytes_consumed, done))
        self.assertEquals('\x00' * 8, result.pending_bytes)

        (bytes_consumed, result, done) = \
            basic_action.consume_output(('\x00' * 3), result)

        self.assertEquals((3, False), (bytes_consumed, done))
        self.assertEquals('', result.pending_bytes)

        (bytes_consumed, result, done) = \
            basic_action.consume_output('\r\n', result)

        self.assertEquals((2, True), (bytes_consumed, done))
        self.assertEquals("OK", result["response"])

    def test_consume_output_varlength(self):
        """ Test for MasterCommandSpec.consume_output with a variable length output field. """
        def dim(byte_value):
            """ Convert a dimmer byte value to the api value. """
            return int(byte_value * 10.0 / 6.0)

        basic_action = MasterCommandSpec("OL", [],
                                [Field("outputs", OutputFieldType()), Field.lit("\r\n\r\n")])

        # Empty outputs
        (bytes_consumed, result, done) = \
            basic_action.consume_output('\x00\r\n\r\n', None)

        self.assertEquals((5, True), (bytes_consumed, done))
        self.assertEquals([], result["outputs"])

        # One output
        (bytes_consumed, result, done) = \
            basic_action.consume_output('\x01\x05\x10\r\n\r\n', None)

        self.assertEquals((7, True), (bytes_consumed, done))
        self.assertEquals([(5, dim(16))], result["outputs"])

        # Split up in multiple parts
        (bytes_consumed, result, done) = \
            basic_action.consume_output('\x03', None)

        self.assertEquals((1, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = \
            basic_action.consume_output('\x05\x10', result)

        self.assertEquals((2, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = \
            basic_action.consume_output('\x01\x02\x03\x04\r\n', result)

        self.assertEquals((6, False), (bytes_consumed, done))

        (bytes_consumed, result, done) = \
            basic_action.consume_output('\r\n', result)

        self.assertEquals((2, True), (bytes_consumed, done))

        self.assertEquals([(5, dim(16)), (1, dim(2)), (3, dim(4))], result["outputs"])

    def test_error_list_field_type(self):
        """ Tests for the ErrorListFieldType. """
        type = ErrorListFieldType()
        # Test with one output module
        input = '\x01O\x14\x00\x01'

        decoded = type.decode(input)
        self.assertEquals([('O20', 1)], decoded)

        self.assertEquals(input, type.encode(decoded))

        # Test with multiple modules
        input = '\x03O\x14\x00\x01I\x20\x01\x01O\x08\x00\x00'

        decoded = type.decode(input)
        self.assertEquals([('O20', 1), ('I32', 257), ('O8', 0)], decoded)

        self.assertEquals(input, type.encode(decoded))

    def test_output_has_crc(self):
        """ Test for MasterCommandSpec.output_has_crc. """
        self.assertFalse(master_api.basic_action().output_has_crc())
        self.assertTrue(master_api.read_output().output_has_crc())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
