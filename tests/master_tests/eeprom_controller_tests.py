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
Tests for the eeprom_controller module.
Created on Sep 2, 2013

@author: fryckbos
'''
import unittest

from master.eeprom_controller import EepromController, EepromFile, EepromModel, EepromAddress, \
                                     EepromData, EepromId, EepromString, EepromByte, EepromWord, \
                                     CompositeDataType, EepromActions, EepromSignedTemp
import master.master_api as master_api


class Model1(EepromModel):
    """ Dummy model with an id. """
    id = EepromId(10)
    name = EepromString(100, lambda id: (1, 2 + id))


class Model2(EepromModel):
    """ Dummy model without an id. """
    name = EepromString(100, (3, 4))


class Model3(EepromModel):
    """ Dummy model with multiple fields. """
    name = EepromString(10, (3, 4))
    link = EepromByte((3, 14))
    out = EepromWord((3, 15))


class Model4(EepromModel):
    """ Dummy model with a dynamic maximum id. """
    id = EepromId(10, address=EepromAddress(0, 0, 1), multiplier=2)
    name = EepromString(10, lambda id: (1, 2 + id * 10))


class Model5(EepromModel):
    """ Dummy model with multiple fields and an id. """
    id = EepromId(3)
    name = EepromString(10, lambda id: (3+id, 4))
    link = EepromByte(lambda id: (3+id, 14))
    out = EepromWord(lambda id: (3+id, 15))


class Model6(EepromModel):
    """ Dummy model with a CompositeDataType. """
    name = EepromString(10, (3, 4))
    status = CompositeDataType([
                            ('link', EepromByte((3, 14))),
                            ('out', EepromWord((3, 15)))])


def get_eeprom_file_dummy(banks):
    """ Create an EepromFile when the data for all banks is provided.

    @param banks: list of string of bytes.
    """
    def list(data):
        """ Dummy for listing a bank. """
        return {"data" : banks[data["bank"]]}

    def write(data):
        """ Dummy for writing bytes to a bank. """
        bank = banks[data["bank"]]
        address = data["address"]
        bytes = data["data"]

        banks[data["bank"]] = bank[0:address] + bytes + bank[address+len(bytes):]

    return EepromFile(MasterCommunicatorDummy(list, write))


class EepromControllerTest(unittest.TestCase):
    """ Tests for EepromController. """

    def test_read(self):
        """ Test read. """
        controller = EepromController(get_eeprom_file_dummy(
                            ["\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249]))
        model = controller.read(Model1, 0)
        self.assertEquals(0, model.id)
        self.assertEquals("hello" + "\x00" * 95, model.name)

        controller = EepromController(get_eeprom_file_dummy(
                            ["", "", "", "\x00" * 4 + "hello" + "\x00" * 249]))
        model = controller.read(Model2)
        self.assertEquals("hello" + "\x00" * 95, model.name)

    def test_read_field(self):
        """ Test read with a field. """
        controller = EepromController(get_eeprom_file_dummy(
                            ["", "", "", "\x00" * 4 + "helloworld\x01\x02\x00" + "\x00" * 239]))
        model = controller.read(Model5, 0, [u"name"])
        self.assertEquals(0, model.id)
        self.assertEquals("helloworld", model.name)
        self.assertFalse("link" in model.__dict__)
        self.assertFalse("out" in model.__dict__)

        model = controller.read(Model5, 0, ["name", "link"])
        self.assertEquals(0, model.id)
        self.assertEquals("helloworld", model.name)
        self.assertEquals(1, model.link)
        self.assertFalse("out" in model.__dict__)

        model = controller.read(Model5, 0, ["name", "out"])
        self.assertEquals(0, model.id)
        self.assertEquals("helloworld", model.name)
        self.assertFalse("link" in model.__dict__)
        self.assertEquals(2, model.out)

        model = controller.read(Model5, 0, ["name", "out", "link"])
        self.assertEquals(0, model.id)
        self.assertEquals("helloworld", model.name)
        self.assertEquals(1, model.link)
        self.assertEquals(2, model.out)

    def test_read_batch(self):
        """ Test read_batch. """
        controller = EepromController(get_eeprom_file_dummy(
                            ["\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249]))

        models = controller.read_batch(Model1, [0, 3, 8])

        self.assertEquals(3, len(models))

        self.assertEquals(0, models[0].id)
        self.assertEquals("hello" + "\x00" * 95, models[0].name)

        self.assertEquals(3, models[1].id)
        self.assertEquals("lo" + "\x00" * 98, models[1].name)

        self.assertEquals(8, models[2].id)
        self.assertEquals("\x00" * 100, models[2].name)

    def test_read_batch_field(self):
        """ Test read_batch with a field. """
        controller = EepromController(get_eeprom_file_dummy(
                        ["", "", "",
                         "\x00" * 4 + "helloworld\x01\x00\x02" + "\x00" * 239,
                         "\x00" * 4 + "secondpage\x02\x00\x03" + "\x00" * 239]))

        models = controller.read_batch(Model5, [0, 1], ["name"])

        self.assertEquals(2, len(models))

        self.assertEquals(0, models[0].id)
        self.assertEquals("helloworld", models[0].name)
        self.assertFalse("link" in models[0].__dict__)
        self.assertFalse("out" in models[0].__dict__)

        self.assertEquals(1, models[1].id)
        self.assertEquals("secondpage", models[1].name)
        self.assertFalse("link" in models[1].__dict__)
        self.assertFalse("out" in models[1].__dict__)

    def test_read_all_without_id(self):
        """ Test read_all for EepromModel without id. """
        controller = EepromController(get_eeprom_file_dummy([]))

        try:
            controller.read_all(Model2)
            self.fail('Expected TypeError.')
        except TypeError as type_error:
            self.assertTrue('id' in str(type_error))

    def test_read_all(self):
        """ Test read_all. """
        controller = EepromController(get_eeprom_file_dummy(
                            ["\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249]))
        models = controller.read_all(Model1)

        self.assertEquals(10, len(models))
        self.assertEquals("hello" + "\x00" * 95, models[0].name)
        self.assertEquals("ello" + "\x00" * 96, models[1].name)
        self.assertEquals("llo" + "\x00" * 97, models[2].name)
        self.assertEquals("lo" + "\x00" * 98, models[3].name)
        self.assertEquals("o" + "\x00" * 99, models[4].name)
        self.assertEquals("\x00" * 100, models[5].name)
        self.assertEquals("\x00" * 100, models[6].name)
        self.assertEquals("\x00" * 100, models[7].name)
        self.assertEquals("\x00" * 100, models[8].name)
        self.assertEquals("\x00" * 100, models[9].name)

    def test_read_all_fields(self):
        """ Test read_all with a field. """
        controller = EepromController(get_eeprom_file_dummy(
                        ["", "", "",
                         "\x00" * 4 + "helloworld\x01\x00\x02" + "\x00" * 239,
                         "\x00" * 4 + "secondpage\x02\x00\x03" + "\x00" * 239,
                         "\x00" * 4 + "anotherone\x04\x00\x05" + "\x00" * 239]))

        models = controller.read_all(Model5, ["name", "link"])

        self.assertEquals(3, len(models))

        self.assertEquals(0, models[0].id)
        self.assertEquals("helloworld", models[0].name)
        self.assertEquals(1, models[0].link)
        self.assertFalse("out" in models[0].__dict__)

        self.assertEquals(1, models[1].id)
        self.assertEquals("secondpage", models[1].name)
        self.assertEquals(2, models[1].link)
        self.assertFalse("out" in models[1].__dict__)

        self.assertEquals(2, models[2].id)
        self.assertEquals("anotherone", models[2].name)
        self.assertEquals(4, models[2].link)
        self.assertFalse("out" in models[2].__dict__)

    def test_get_max_id(self):
        """ Test get_max_id. """
        controller = EepromController(get_eeprom_file_dummy(["\x05" + "\x00" * 254]))
        self.assertEquals(10, controller.get_max_id(Model4))

        controller = EepromController(get_eeprom_file_dummy(["\x10" + "\x00" * 254]))
        self.assertEquals(32, controller.get_max_id(Model4))

        controller = EepromController(get_eeprom_file_dummy([]))
        self.assertEquals(10, controller.get_max_id(Model1))

        try:
            controller.get_max_id(Model2)
            self.fail('Expected TypeError.')
        except TypeError as type_error:
            self.assertTrue('id' in str(type_error))

    def test_write(self):
        """ Test write. """
        controller = EepromController(get_eeprom_file_dummy(
                                ["\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256]))
        controller.write(Model1(id=1, name="Hello world !" + "\xff" * 10))

        model = controller.read(Model1, 1)
        self.assertEquals(1, model.id)
        self.assertEquals("Hello world !", model.name)

    def test_write_sparse(self):
        """ Test write when not all fields of the model are provided. """
        controller = EepromController(get_eeprom_file_dummy(
                                ["\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256]))
        controller.write(Model5(id=0, name="Helloworld"))

        model = controller.read(Model5, 0)
        self.assertEquals(0, model.id)
        self.assertEquals("Helloworld", model.name)
        self.assertEquals(0, model.link)
        self.assertEquals(0, model.out)

        controller.write(Model5(id=0, name="Helloworld", link=1))

        model = controller.read(Model5, 0)
        self.assertEquals(0, model.id)
        self.assertEquals("Helloworld", model.name)
        self.assertEquals(1, model.link)
        self.assertEquals(0, model.out)

    def test_write_batch_one(self):
        """ Test write_batch with one model. """
        controller = EepromController(get_eeprom_file_dummy(
                                ["\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256]))
        controller.write_batch([Model1(id=3, name="Hello world !")])

        model = controller.read(Model1, 3)
        self.assertEquals(3, model.id)
        self.assertEquals("Hello world !", model.name)

    def test_write_batch_multiple(self):
        """ Test write with multiple models. """
        controller = EepromController(get_eeprom_file_dummy(
                                ["\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256]))
        controller.write_batch([Model1(id=3, name="First model"),
                                Model2(name="Second model" + "\x01" * 88)])

        model = controller.read(Model1, 3)
        self.assertEquals(3, model.id)
        self.assertEquals("First model", model.name)

        model = controller.read(Model2)
        self.assertEquals("Second model" + "\x01" * 88, model.name)


class MasterCommunicatorDummy(object):
    """ Dummy for the MasterCommunicator. """

    def __init__(self, list_function=None, write_function=None):
        """ Default constructor. """
        self.__list_function = list_function
        self.__write_function = write_function

    def do_command(self, cmd, data):
        """ Execute a command on the master dummy. """
        if cmd == master_api.eeprom_list():
            return self.__list_function(data)
        elif cmd == master_api.read_eeprom():
            bank = self.__list_function(data)["data"]
            return {"data" : bank[data["addr"] : data["addr"] + data["num"]]}
        elif cmd == master_api.write_eeprom():
            return self.__write_function(data)
        elif cmd == master_api.activate_eeprom():
            return {"eep" : 0, "resp" : "OK"}
        else:
            raise Exception("Command %s not found" % cmd)


class EepromFileTest(unittest.TestCase):
    """ Tests for EepromFile. """

    def test_read_one_bank_one_address(self):
        """ Test read from one bank with one address """
        def read(data):
            """ Read dummy. """
            if data["bank"] == 1:
                return {"data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48}
            else:
                raise Exception("Wrong page")

        eeprom_file = EepromFile(MasterCommunicatorDummy(read))
        address = EepromAddress(1, 0, 3)
        data = eeprom_file.read([address])

        self.assertEquals(1, len(data))
        self.assertEquals(address, data[0].address)
        self.assertEquals("abc", data[0].bytes)

    def test_read_one_bank_two_addresses(self):
        """ Test read from one bank with two addresses. """
        def read(data):
            """ Read dummy """
            if data["bank"] == 1:
                return {"data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48}
            else:
                raise Exception("Wrong page")

        eeprom_file = EepromFile(MasterCommunicatorDummy(read))

        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(1, 203, 4)
        data = eeprom_file.read([address1, address2])

        self.assertEquals(2, len(data))

        self.assertEquals(address1, data[0].address)
        self.assertEquals("c" + "\xff" * 9, data[0].bytes)

        self.assertEquals(address2, data[1].address)
        self.assertEquals("def\xff", data[1].bytes)

    def test_read_multiple_banks(self):
        """ Test read from multiple banks. """
        def read(data):
            """ Read dummy. """
            if data["bank"] == 1:
                return {"data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48}
            if data["bank"] == 100:
                return {"data" : "hello" + "\x00" * 100 + "world" + "\x00" * 146}
            else:
                raise Exception("Wrong page")

        eeprom_file = EepromFile(MasterCommunicatorDummy(read))

        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(100, 4, 10)
        address3 = EepromAddress(100, 105, 5)
        data = eeprom_file.read([address1, address2, address3])

        self.assertEquals(3, len(data))

        self.assertEquals(address1, data[0].address)
        self.assertEquals("c" + "\xff" * 9, data[0].bytes)

        self.assertEquals(address2, data[1].address)
        self.assertEquals("o" + "\x00" * 9, data[1].bytes)

        self.assertEquals(address3, data[2].address)
        self.assertEquals("world", data[2].bytes)

    def test_write_single_field(self):
        """ Write a single field to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data["bank"] == 1:
                done['read1'] = True
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Wrong page")

        def write(data):
            """ Write dummy. """
            self.assertEquals(1, data["bank"])
            self.assertEquals(2, data["address"])
            self.assertEquals("abc", data["data"])
            done['write'] = True

        communicator = MasterCommunicatorDummy(read, write)

        eeprom_file = EepromFile(communicator)
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), "abc")])

        self.assertTrue('read1' in done)
        self.assertTrue('write' in done)

    def test_write_multiple_fields(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data["bank"] == 1:
                done['read1'] = True
                return {"data" : "\xff" * 256}
            elif data["bank"] == 2:
                done['read2'] = True
                return {"data" : "\x00" * 256}
            else:
                raise Exception("Wrong page")

        def write(data):
            """ Write dummy. """
            if 'write1' not in done:
                done['write1'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(2, data["address"])
                self.assertEquals("abc", data["data"])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEquals(2, data["bank"])
                self.assertEquals(123, data["address"])
                self.assertEquals("More bytes", data["data"])
            elif 'write3' not in done:
                done['write3'] = True
                self.assertEquals(2, data["bank"])
                self.assertEquals(133, data["address"])
                self.assertEquals(" than 10", data["data"])
            else:
                raise Exception("Too many writes")

        communicator = MasterCommunicatorDummy(read, write)

        eeprom_file = EepromFile(communicator)
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), "abc"),
                    EepromData(EepromAddress(2, 123, 18), "More bytes than 10")])

        self.assertTrue('read1' in done)
        self.assertTrue('read2' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)
        self.assertTrue('write3' in done)

    def test_write_multiple_fields_same_batch(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}

        def read(data):
            """ Read dummy. """
            if data["bank"] == 1:
                done['read'] = True
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Wrong page")

        def write(data):
            """ Write dummy. """
            if 'write1' not in done:
                done['write1'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(2, data["address"])
                self.assertEquals("abc\xff\xff\xffdefg", data["data"])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(12, data["address"])
                self.assertEquals("hijklmn", data["data"])
            else:
                raise Exception("Too many writes")

        communicator = MasterCommunicatorDummy(read, write)

        eeprom_file = EepromFile(communicator)
        eeprom_file.write([EepromData(EepromAddress(1, 2, 3), "abc"),
                           EepromData(EepromAddress(1, 8, 11), "defghijklmn")])

        self.assertTrue('read' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)

    def test_cache(self):
        """ Test the caching of banks. """
        state = { 'count' : 0 }

        def read(data):
            """ Read dummy. """
            if state['count'] == 0:
                state['count'] = 1
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Too many reads !")

        communicator = MasterCommunicatorDummy(read, None)

        eeprom_file = EepromFile(communicator)
        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        # Second read should come from cache, if read is called
        # an exception will be thrown.
        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

    def test_cache_invalidate(self):
        """ Test the cache invalidation. """
        state = { 'count' : 0 }

        def read(data):
            """ Read dummy. """
            if state['count'] == 0:
                state['count'] = 1
                return {"data" : "\xff" * 256}
            elif state['count'] == 1:
                state['count'] = 2
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Too many reads !")

        communicator = MasterCommunicatorDummy(read, None)

        eeprom_file = EepromFile(communicator)
        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        # Second read should come from cache.
        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        eeprom_file.invalidate_cache()
        # Should be read from communicator, since cache is invalid
        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        self.assertEquals(2, state['count'])

    def test_cache_write(self):
        """ Test the eeprom cache on writing. """
        state = {'read' : 0, 'write' : 0}

        def read(data):
            """ Read dummy. """
            if state['read'] == 0:
                state['read'] = 1
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Too many reads !")

        def write(data):
            """ Write dummy. """
            if state['write'] == 0:
                self.assertEquals(1, data["bank"])
                self.assertEquals(100, data["address"])
                self.assertEquals("\x00" * 10, data["data"])
                state['write'] = 1
            elif state['write'] == 1:
                self.assertEquals(1, data["bank"])
                self.assertEquals(110, data["address"])
                self.assertEquals("\x00" * 10, data["data"])
                state['write'] = 2
            else:
                raise Exception("Too many writes !")

        communicator = MasterCommunicatorDummy(read, write)
        eeprom_file = EepromFile(communicator)

        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        eeprom_file.write([EepromData(EepromAddress(1, 100, 20), "\x00" * 20)])

        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 100 + "\x00" * 20 + "\xff" * 136, read[0].bytes)

        self.assertEquals(1, state['read'])
        self.assertEquals(2, state['write'])

    def test_cache_write_exception(self):
        """ The cache should be invalidated if a write fails. """
        state = {'read' : 0, 'write' : 0}

        def read(data):
            """ Read dummy. """
            if state['read'] == 0:
                state['read'] = 1
                return {"data" : "\xff" * 256}
            elif state['read'] == 1:
                state['read'] = 2
                return {"data" : "\xff" * 256}
            else:
                raise Exception("Too many reads !")

        def write(data):
            """ Write dummy. """
            state['write'] += 1
            raise Exception("write fails...")

        communicator = MasterCommunicatorDummy(read, write)
        eeprom_file = EepromFile(communicator)

        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        try:
            eeprom_file.write([EepromData(EepromAddress(1, 100, 20), "\x00" * 20)])
            self.fail("Should not get here !")
        except Exception as exception:
            pass

        read = eeprom_file.read([EepromAddress(1, 0, 256)])
        self.assertEquals("\xff" * 256, read[0].bytes)

        self.assertEquals(2, state['read'])
        self.assertEquals(1, state['write'])


class EepromModelTest(unittest.TestCase):
    """ Tests for EepromModel. """

    def test_get_fields(self):
        """ Test get_fields. """
        fields = Model1.get_fields()

        self.assertEquals(1, len(fields))
        self.assertEquals("name", fields[0][0])

        fields = Model1.get_fields(include_id=True)

        self.assertEquals(2, len(fields))
        self.assertEquals("id", fields[0][0])
        self.assertEquals("name", fields[1][0])

        fields = Model6.get_fields()

        self.assertEquals(2, len(fields))
        self.assertEquals("name", fields[0][0])
        self.assertEquals("status", fields[1][0])


    def test_has_id(self):
        """ Test has_id. """
        self.assertTrue(Model1.has_id())
        self.assertFalse(Model2.has_id())

    def test_get_name(self):
        """ Test get_name. """
        self.assertEquals("Model1", Model1.get_name())
        self.assertEquals("Model2", Model2.get_name())

    def test_check_id(self):
        """ Test check_id. """
        Model1.check_id(0) ## Should just work

        try:
            Model1.check_id(100)
            self.fail("Expected TypeError")
        except TypeError as type_error:
            self.assertTrue("maximum" in str(type_error))

        try:
            Model1.check_id(None)
            self.fail("Expected TypeError")
        except TypeError as type_erro:
            self.assertTrue("id" in str(type_erro))

        Model2.check_id(None) ## Should just work

        try:
            Model2.check_id(0)
            self.fail("Expected TypeError")
        except TypeError as type_erro:
            self.assertTrue("id" in str(type_erro))

    def test_to_dict(self):
        """ Test to_dict. """
        self.assertEquals({'id':1, 'name':'test'}, Model1(id=1, name="test").to_dict())
        self.assertEquals({'name':'hello world'}, Model2(name="hello world").to_dict())
        self.assertEquals({'name':'a', 'status':[1, 2]}, Model6(name="a", status=[1, 2]).to_dict())

    def test_from_dict(self):
        """ Test from_dict. """
        model1 = Model1.from_dict({'id':1, 'name':u'test'})
        self.assertEquals(1, model1.id)
        self.assertEquals('test', model1.name)

        model2 = Model2.from_dict({'name':'test'})
        self.assertEquals('test', model2.name)

        model6 = Model6.from_dict({'name':u'test', 'status':[1, 2]})
        self.assertEquals('test', model6.name)
        self.assertEquals([1, 2], model6.status)

    def test_from_dict_error(self):
        """ Test from_dict when the dict does not contain the right keys. """
        try:
            Model1.from_dict({'id':1, 'junk':'test'})
            self.fail("Should have received TypeError")
        except TypeError as type_error:
            self.assertTrue("junk" in str(type_error))

        try:
            Model1.from_dict({'name':'test'})
            self.fail("Should have received TypeError")
        except TypeError as type_error:
            self.assertTrue("id" in str(type_error))

    def test_to_eeprom_data(self):
        """ Test to_eeprom_data. """
        model1 = Model1(id=1, name=u"test")
        data = model1.to_eeprom_data()

        self.assertEquals(1, len(data))
        self.assertEquals(1, data[0].address.bank)
        self.assertEquals(3, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)

        model2 = Model2(name="test")
        data = model2.to_eeprom_data()

        self.assertEquals(1, len(data))
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(4, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)

        model3 = Model3(name="test", link=123, out=456)
        data = model3.to_eeprom_data()

        self.assertEquals(3, len(data))

        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(14, data[0].address.offset)
        self.assertEquals(1, data[0].address.length)
        self.assertEquals(str(chr(123)), data[0].bytes)

        self.assertEquals(3, data[1].address.bank)
        self.assertEquals(4, data[1].address.offset)
        self.assertEquals(10, data[1].address.length)
        self.assertEquals("test" + "\xff" * 6, data[1].bytes)

        self.assertEquals(3, data[2].address.bank)
        self.assertEquals(15, data[2].address.offset)
        self.assertEquals(2, data[2].address.length)
        self.assertEquals(str(chr(200) + chr(1)), data[2].bytes)

        model6 = Model6(name=u"test", status=[1, 2])
        data = model6.to_eeprom_data()

        self.assertEquals(3, len(data))
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(4, data[0].address.offset)
        self.assertEquals(10, data[0].address.length)
        self.assertEquals("test" + "\xff" * 6, data[0].bytes)

        self.assertEquals(3, data[1].address.bank)
        self.assertEquals(14, data[1].address.offset)
        self.assertEquals(1, data[1].address.length)
        self.assertEquals(str(chr(1)), data[1].bytes)

        self.assertEquals(3, data[2].address.bank)
        self.assertEquals(15, data[2].address.offset)
        self.assertEquals(2, data[2].address.length)
        self.assertEquals("\x02\x00", data[2].bytes)


    def test_to_eeprom_data_readonly(self):
        """ Test to_eeprom_data with a read only field. """
        class RoModel(EepromModel):
            """ Dummy model. """
            id = EepromId(10)
            name = EepromString(100, lambda id: (1, 2 + id))
            other = EepromByte((0, 0), read_only=True)

        model = RoModel(id=1, name=u"test", other=4)
        data = model.to_eeprom_data()

        self.assertEquals(1, len(data))
        self.assertEquals(1, data[0].address.bank)
        self.assertEquals(3, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)

    def test_from_eeprom_data(self):
        """ Test from_eeprom_data. """
        model1_data = [EepromData(EepromAddress(1, 3, 100), "test" + "\xff" * 96)]
        model1 = Model1.from_eeprom_data(model1_data, 1)
        self.assertEquals(1, model1.id)
        self.assertEquals("test", model1.name)

        model2_data = [EepromData(EepromAddress(3, 4, 100), "hello world" + "\xff" * 89)]
        model2 = Model2.from_eeprom_data(model2_data)
        self.assertEquals("hello world", model2.name)

        model3_data = [EepromData(EepromAddress(3, 4, 10), "hello worl"),
                       EepromData(EepromAddress(3, 14, 1), str(chr(123))),
                       EepromData(EepromAddress(3, 15, 2), str(chr(200) + chr(1)))]
        model3 = Model3.from_eeprom_data(model3_data)
        self.assertEquals("hello worl", model3.name)
        self.assertEquals(123, model3.link)
        self.assertEquals(456, model3.out)

        model6_data = [EepromData(EepromAddress(3, 4, 10), "test" + "\xff" * 6),
                       EepromData(EepromAddress(3, 14, 1), str(chr(1))),
                       EepromData(EepromAddress(3, 15, 2), str(chr(2) + chr(0)))]
        model6 = Model6.from_eeprom_data(model6_data)

        self.assertEquals("test", model6.name)
        self.assertEquals([1, 2], model6.status)

    def test_from_eeprom_wrong_address(self):
        """ Test from_eeprom_data with wrong address. """
        try:
            model1_data = [EepromData(EepromAddress(3, 4, 100), "test" + "\xff" * 96)]
            Model1.from_eeprom_data(model1_data, 1)
            self.fail("Should have receive KeyError.")
        except KeyError as key_error:
            self.assertTrue("(B1 A3 L100)" in str(key_error))

    def test_from_eeprom_wrong_data(self):
        """ Test from_eeprom_data with wrong data. """

        try:
            model3_data = [EepromData(EepromAddress(3, 4, 10), "hello worljkfdsjklsadfjklsadf"),
                           EepromData(EepromAddress(3, 14, 1), str(chr(123))),
                           EepromData(EepromAddress(3, 15, 2), str(chr(1) + chr(200)))]

            Model3.from_eeprom_data(model3_data)
            self.fail("Should have receive TypeError.")
        except TypeError as type_error:
            self.assertTrue("Length" in str(type_error))

    def test_get_addresses(self):
        """ Test get_addresses. """
        addresses = Model1.get_addresses(1)

        self.assertEquals(1, len(addresses))
        self.assertEquals(1, addresses[0].bank)
        self.assertEquals(3, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)

        addresses = Model2.get_addresses()

        self.assertEquals(1, len(addresses))
        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(4, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)

        addresses = Model3.get_addresses()

        self.assertEquals(3, len(addresses))

        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(14, addresses[0].offset)
        self.assertEquals(1, addresses[0].length)

        self.assertEquals(3, addresses[1].bank)
        self.assertEquals(4, addresses[1].offset)
        self.assertEquals(10, addresses[1].length)

        self.assertEquals(3, addresses[2].bank)
        self.assertEquals(15, addresses[2].offset)
        self.assertEquals(2, addresses[2].length)

        addresses = Model6.get_addresses()
        self.assertEquals(3, len(addresses))

        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(4, addresses[0].offset)
        self.assertEquals(10, addresses[0].length)

        self.assertEquals(3, addresses[1].bank)
        self.assertEquals(14, addresses[1].offset)
        self.assertEquals(1, addresses[1].length)

        self.assertEquals(3, addresses[2].bank)
        self.assertEquals(15, addresses[2].offset)
        self.assertEquals(2, addresses[2].length)

    def test_get_addresses_wrong_id(self):
        """ Test get_addresses with a wrong id. """
        try:
            Model1.get_addresses(None)
            self.fail("Expected TypeError.")
        except TypeError as type_error:
            self.assertTrue("id" in str(type_error))


class CompositeDataTypeTest(unittest.TestCase):
    """ Tests for CompositeDataType. """

    def test_get_addresses(self):
        """ Test get_addresses. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])
        addresses = cdt.get_addresses()

        self.assertEquals(2, len(addresses))

        self.assertEquals(1, addresses[0].bank)
        self.assertEquals(2, addresses[0].offset)
        self.assertEquals(1, addresses[0].length)

        self.assertEquals(1, addresses[1].bank)
        self.assertEquals(3, addresses[1].offset)
        self.assertEquals(1, addresses[1].length)

    def test_get_addresses_id(self):
        """ Test get_addresses with an id. """
        cdt = CompositeDataType([('one', EepromByte(lambda id: (1, 10+id))),
                                 ('two', EepromByte(lambda id: (1, 20+id)))])
        addresses = cdt.get_addresses(id=5)

        self.assertEquals(2, len(addresses))

        self.assertEquals(1, addresses[0].bank)
        self.assertEquals(15, addresses[0].offset)
        self.assertEquals(1, addresses[0].length)

        self.assertEquals(1, addresses[1].bank)
        self.assertEquals(25, addresses[1].offset)
        self.assertEquals(1, addresses[1].length)

    def test_get_name(self):
        """ Test get_name. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])
        self.assertEquals("[one(Byte),two(Byte)]", cdt.get_name())

    def test_from_data_dict(self):
        """ Test from_data_dict. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])

        addr1 = EepromAddress(1, 2, 1)
        addr2 = EepromAddress(1, 3, 1)

        data_dict = {addr1 : EepromData(addr1, str(chr(12))),
                     addr2 : EepromData(addr2, str(chr(34)))}
        self.assertEquals([12, 34], cdt.from_data_dict(data_dict))

    def test_to_eeprom_data(self):
        """ Test to_eeprom_data. """
        cdt = CompositeDataType([('one', EepromByte((1, 2))), ('two', EepromByte((1, 3)))])

        data = cdt.to_eeprom_data([34, 12])

        self.assertEquals(2, len(data))

        self.assertEquals(EepromAddress(1, 2, 1), data[0].address)
        self.assertEquals(str(chr(34)), data[0].bytes)

        self.assertEquals(EepromAddress(1, 3, 1), data[1].address)
        self.assertEquals(str(chr(12)), data[1].bytes)

    def test_is_writable(self):
        """ Test is_writable """
        cdt = CompositeDataType([])
        self.assertTrue(cdt.is_writable())
        cdt = CompositeDataType([], False)
        self.assertTrue(cdt.is_writable())
        cdt = CompositeDataType([], True)
        self.assertFalse(cdt.is_writable())


class EepromActionsTest(unittest.TestCase):
    """ Tests for EepromActions. """

    def test_from_bytes(self):
        """ Test from_bytes. """
        actions = EepromActions(1, (0, 0))
        self.assertEquals("1,2", actions.from_bytes("\x01\x02"))

        actions = EepromActions(2, (0, 0))
        self.assertEquals("1,2", actions.from_bytes("\x01\x02\xff\xff"))

    def test_to_bytes(self):
        """ Test to_bytes. """
        actions = EepromActions(1, (0, 0))
        self.assertEquals("\x01\x02", actions.to_bytes("1,2"))

        actions = EepromActions(2, (0, 0))
        self.assertEquals("\x01\x02\xff\xff", actions.to_bytes("1,2"))


class EepromSignedTempTest(unittest.TestCase):
    """ Tests for EepromSignedTemp. """

    def test_from_bytes(self):
        """ Test from_bytes. """
        temp = EepromSignedTemp((0, 0))
        self.assertEquals(0.0, temp.from_bytes("\xff"))
        self.assertEquals(1.0, temp.from_bytes("\x02"))
        self.assertEquals(-1.0, temp.from_bytes("\x82"))
        self.assertEquals(7.5, temp.from_bytes("\x0f"))
        self.assertEquals(-7.5, temp.from_bytes("\x8f"))

    def test_to_bytes(self):
        """ Test to_bytes. """
        temp = EepromSignedTemp((0, 0))
        self.assertEquals("\xff", temp.to_bytes(0.0))
        self.assertEquals("\x02", temp.to_bytes(1.0))
        self.assertEquals("\x82", temp.to_bytes(-1.0))
        self.assertEquals("\x0f", temp.to_bytes(7.5))
        self.assertEquals("\x8f", temp.to_bytes(-7.5))

    def test_to_bytes_out_of_range(self):
        """ Test to_bytes with out of range values. """
        temp = EepromSignedTemp((0, 0))

        try:
            temp.to_bytes(8)
            self.fail("Expected ValueError.")
        except ValueError:
            pass

        try:
            temp.to_bytes(45)
            self.fail("Expected ValueError.")
        except ValueError:
            pass

        try:
            temp.to_bytes(-8)
            self.fail("Expected ValueError.")
        except ValueError:
            pass

        try:
            temp.to_bytes(-89)
            self.fail("Expected ValueError.")
        except ValueError:
            pass


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
