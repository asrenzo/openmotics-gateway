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
Contains controller from reading and writing to the Master EEPROM.

Created on Sep 2, 2013

@author: fryckbos
'''
import inspect
import types

from master_api import eeprom_list, read_eeprom, write_eeprom, activate_eeprom


class EepromController(object):
    """ The controller takes EepromModels and reads or writes them from and to an EepromFile. """

    def __init__(self, eeprom_file):
        """ Constructor takes the eeprom_file for reading and writes.

        :param eeprom_file: instance of EepromFile.
        """
        self.__eeprom_file = eeprom_file

    def invalidate_cache(self):
        """ Invalidate the cache, this should happen when maintenance mode was used. """
        self.__eeprom_file.invalidate_cache()

    def read(self, eeprom_model, id=None, fields=None):
        """ Create an instance of an EepromModel by reading it from the EepromFile. The id has to
        be specified if the model has an EepromId field.

        :param eeprom_model: EepromModel class
        :param id: optional parameter (integer)
        """
        eeprom_model.check_id(id)

        addresses = eeprom_model.get_addresses(id, fields)
        eeprom_data = self.__eeprom_file.read(addresses)

        return eeprom_model.from_eeprom_data(eeprom_data, id, fields)

    def read_batch(self, eeprom_model, ids, fields=None):
        """ Create a list of instances of an EepromModel by reading it from the EepromFile.

        :param eeprom_model: EepromModel class
        :param id: list of integers
        """
        for id in ids:
            eeprom_model.check_id(id)

        addresses = []
        for id in ids:
            addresses.extend(eeprom_model.get_addresses(id, fields))

        eeprom_data = self.__eeprom_file.read(addresses)

        i = 0
        out = []

        for id in ids:
            length = len(eeprom_model.get_addresses(id, fields))
            out.append(eeprom_model.from_eeprom_data(eeprom_data[i:i + length], id, fields))
            i += length

        return out

    def read_all(self, eeprom_model, fields=None):
        """ Create a list of instance of an EepromModel by reading all ids of that model from the
        EepromFile. Only applicable for EepromModels with an EepromId.

        :type eeprom_model: EepromModel class
        """
        return self.read_batch(eeprom_model, range(self.get_max_id(eeprom_model)), fields)

    def write(self, eeprom_model):
        """ Write a given EepromModel to the EepromFile.

        :param eeprom_model: instance of EepromModel.
        """
        eeprom_data = eeprom_model.to_eeprom_data()
        self.__eeprom_file.write(eeprom_data)
        self.__eeprom_file.activate()

    def write_batch(self, eeprom_models):
        """ Write a list of EepromModel instances to the EepromFile.

        :param eeprom_models: list of EepromModel instances.
        """
        eeprom_data = []
        for eeprom_model in eeprom_models:
            eeprom_data.extend(eeprom_model.to_eeprom_data())

        self.__eeprom_file.write(eeprom_data)
        self.__eeprom_file.activate()

    def get_max_id(self, eeprom_model):
        """ Get the maximum id for an eeprom_model.

        :param eeprom_mode: instance of EepromModel.
        """
        if not eeprom_model.has_id():
            raise TypeError("EepromModel %s does not contain an id" % eeprom_model.get_name())
        else:
            eeprom_id = eeprom_model.__dict__[eeprom_model.get_id_field()]

            if not eeprom_id.has_address():
                return eeprom_id.get_max_id()
            else:
                address = eeprom_id.get_address()
                if address.length != 1:
                    raise TypeError("Length of max id address in EepromModel %s is not 1" %
                                    eeprom_model.get_name())

                eeprom_data = self.__eeprom_file.read([address])
                max_id = ord(eeprom_data[0].bytes[0])

                return max_id * eeprom_id.get_multiplier()


class EepromFile(object):
    """ Reads from and writes to the Master EEPROM. """

    BATCH_SIZE = 10

    def __init__(self, master_communicator):
        """ Create an EepromFile.

        :param master_communicator: communicates with the master.
        :type master_communicator: instance of MasterCommunicator.
        """
        self.__master_communicator = master_communicator
        self.__bank_cache = dict()

    def invalidate_cache(self):
        """ Invalidate the cache, this should happen when maintenance mode was used. """
        self.__bank_cache = dict()

    def activate(self):
        """ Activate a change in the Eeprom. The master will read the eeprom
        and adjust the current settings.
        """
        self.__master_communicator.do_command(activate_eeprom(), {'eep' : 0})

    def read(self, addresses):
        """ Read data from the Eeprom.

        :param addresses: the addresses to read.
        :type addresses: list of EepromAddress instances.
        :returns: a list of EepromData instances (in the same order as the provided addresses).
        """
        ## Group the addresses per bank
        per_bank = dict()
        for addr in addresses:
            if addr.bank not in per_bank:
                per_bank[addr.bank] = []
            per_bank[addr.bank].append(addr)

        ## Read the bank data
        bank_data = dict()
        for bank in per_bank:
            bank_data[bank] = self.__read_bank(bank, per_bank[bank])

        ## Extract the required bytes from the bank data
        return [EepromData(a, bank_data[a.bank][a.offset : a.offset + a.length])
                for a in addresses]

    def __read_bank(self, bank, addresses):
        """ Read a list of addresses from a bank, this returns a list of 256 bytes. Only the bytes
        described in the addresses are valid, the other bytes might be dummies. The master_api
        provides two function for reading from the eeprom: master_api.eeprom_list() and
        master_api.read_eeprom(). The list reads a full bank (256 bytes), while the read can only
        read 10 bytes at once. Due to communciation overhead the read function is about half the
        speed (per byte) of the list function. Howver the list function is cached while the read
        function is not. If more than 6 reads are required for 1 bank, the list function is used
        to read the bank at once.

        :param bank: the number of the bank
        :type bank: Integer
        :param addresses: the addresses in the bank to read
        :type addresses: a list of EepromAddress instances
        :returns: list of 256 bytes.
        """
        ## Mark the bytes that should be read
        read_map = [False] * 256
        for addr in addresses:
            for i in range(addr.offset, addr.offset + addr.length):
                read_map[i] = True

        ## Find the start addresses of the reads
        start_addresses = []
        i = 0
        while i < 256:
            if read_map[i] is True:
                if i > 256 - EepromFile.BATCH_SIZE:
                    ## This is the last possible start address
                    i = 256 - EepromFile.BATCH_SIZE
                start_addresses.append(i)
                i += EepromFile.BATCH_SIZE
            else:
                i += 1

        ## Read from the start addresses
        if len(start_addresses) > 6:
            ## Too many reads, better read the whole bank at once using eeprom_list.
            return self.__read_banks([bank])[bank]
        else:
            ## Fill the bytes with dummies and only read the required bytes from eeprom.
            bytes = ["\xff"] * 256

            for addr in start_addresses:
                read = self.__master_communicator.do_command(
                    read_eeprom(), {"bank" : bank, "addr" : addr, "num" : EepromFile.BATCH_SIZE})

                bytes[addr : addr + EepromFile.BATCH_SIZE] = read["data"]

            return ''.join(bytes)

    def __read_banks(self, banks):
        """ Read a number of banks from the Eeprom.

        :param banks: a list of banks (integers).
        :returns: a dict mapping the bank to the data.
        """
        ret = dict()

        for bank in banks:
            if bank in self.__bank_cache:
                data = self.__bank_cache[bank]
            else:
                output = self.__master_communicator.do_command(eeprom_list(), {"bank" : bank})
                data = output['data']
                self.__bank_cache[bank] = data

            ret[bank] = data

        return ret

    def write(self, data):
        """ Write data to the Eeprom.

        :param data: the data to write.
        :type data: list of EepromData instances.
        """
        # Read the data in the banks that we are trying to write
        bank_data = self.__read_banks(set([d.address.bank for d in data]))
        new_bank_data = bank_data.copy()

        for data_piece in data:
            self.__patch(new_bank_data, data_piece)

        # Check what changed and write changes in batch
        try:
            for bank in bank_data.keys():
                old = bank_data[bank]
                new = new_bank_data[bank]
    
                i = 0
                while i < len(bank_data[bank]):
                    if old[i] != new[i]:
                        length = 1
                        j = 1
                        while j < EepromFile.BATCH_SIZE:
                            if old[i + j] != new[i + j]:
                                length = j + 1
                            j += 1
    
                        self.__write(bank, i, new[i:i + length])
                        i += EepromFile.BATCH_SIZE
                    else:
                        i += 1
    
                self.__bank_cache[bank] = new
        except Exception as exception:
            ## The write failed at some point, we are not sure about the data in the cache,
            ## so we invalidate it.
            self.invalidate_cache()
            raise exception

    def __patch(self, bank_data, eeprom_data):
        """ Patch a byte array with a eeprom_data.

        :param bank_data: dict with bank data, key = bank, data = bytes in the bank.
        :param eeprom_data: instance of EepromData.
        """
        address = eeprom_data.address
        data = bank_data[address.bank]
        bank_data[address.bank] = data[0:address.offset] \
                                  + eeprom_data.bytes \
                                  + data[address.offset + address.length:]

    def __write(self, bank, offset, to_write):
        """ Write a byte array to a specific location defined by the bank and the offset. """
        self.__master_communicator.do_command(
                write_eeprom(), {"bank" : bank, "address": offset, "data": to_write})


class EepromAddress(object):
    """ Represents an address in the Eeprom, has a bank, an offset and a length. """

    def __init__(self, bank, offset, length):
        self.bank = bank
        self.offset = offset
        self.length = length

    def __eq__(self, other):
        return self.bank == other.bank \
               and self.offset == other.offset \
               and self.length == other.length

    def __hash__(self):
        return self.bank + self.offset * 256 + self.length * 256 * 256

    def __str__(self):
        return "(B%d A%d L%d)" % (self.bank, self.offset, self.length)

    def __repr__(self):
        return self.__str__()


class EepromData(object):
    """ A piece of Eeprom data, has an address and the actual data. """

    def __init__(self, address, bytes):
        if address.length != len(bytes):
            raise TypeError("Length in the address (%d) does not match the number of bytes (%d)" %
                            (address.length, len(bytes)))

        self.address = address
        self.bytes = bytes

    def __str__(self):
        hex = " ".join(['%3d' % ord(c) for c in self.bytes])
        readable = "".join([c if ord(c) > 32 and ord(c) <= 126 else '.' for c in self.bytes])
        return "%s : %s | %s" % (self.address, hex, readable)

    def __repr__(self):
        return self.__str__()


class EepromModel(object):
    """ The EepromModel provides a generic way to model data in the eeprom by creating a child
    class of EepromModel with an optional EepromId and EepromDataTypes as class fields.
    """

    def __init__(self, **kwargs):
        """ The arguments to the constructor are defined by the EepromDataType class fields. """
        fields = [x[0] for x in self.__class__.get_fields(include_id=True)]

        for (field, value) in kwargs.items():
            if field in fields:
                self.__dict__[field] = value
            else:
                raise TypeError("Field %s is unknown for %s" % (field, self.__class__.__name__))

        id_field_name = self.__class__.get_id_field()
        if id_field_name != None and id_field_name not in kwargs:
            raise TypeError("The id was missing for %s" % self.__class__.__name__)

    @classmethod
    def get_fields(cls, include_id=False):
        """ Get the fields defined by an EepromModel child. """
        return inspect.getmembers(cls,
                                  lambda x: isinstance(x, EepromDataType) or
                                            isinstance(x, CompositeDataType) or
                                            (include_id and isinstance(x, EepromId)))

    @classmethod
    def get_field_dict(cls, include_id=False):
        """ Get a dict from the field name to the field type for each field defined by the
        EepromModel child.
        """
        class_field_dict = {}
        for (name, type) in cls.get_fields(include_id):
            class_field_dict[name] = type

        return class_field_dict

    @classmethod
    def get_id_field(cls):
        """ Get the name of the EepromId field. None if not included. """
        if cls.has_id():
            ids = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
            return ids[0][0]
        else:
            return None

    @classmethod
    def has_id(cls):
        """ Check if the EepromModel has an id. """
        ids = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
        if len(ids) == 0:
            return False
        elif len(ids) == 1:
            return True
        else:
            raise TypeError("Found more than 1 EepromId for %s" % cls.__name__)

    @classmethod
    def get_name(cls):
        """ Get the name of the EepromModel. """
        return cls.__name__

    @classmethod
    def check_id(cls, id):
        """ Check if the id is valid for this EepromModel. """
        has_id = cls.has_id()

        if id is None and has_id:
            raise TypeError("%s has an id, but no id was given." % cls.__name__)
        elif id is not None and not has_id:
            raise TypeError("%s doesn't have an id, but id was given." % cls.__name__)
        elif id is not None:
            id_type = inspect.getmembers(cls, lambda x: isinstance(x, EepromId))
            max_id = id_type[0][1].get_max_id()

            if id > max_id:
                raise TypeError("The maximum id for %s is %d, %d was provided." %
                                (cls.__name__, max_id, id))

    def to_dict(self):
        """ Create a model dict from the EepromModel. """
        out = dict()

        for (field_name, _) in self.__class__.get_fields(include_id=True):
            if field_name in self.__dict__:
                out[field_name] = self.__dict__[field_name]

        return out

    @classmethod
    def from_dict(cls, in_dict):
        """ Create an EepromModel from a dict. """
        return cls(**in_dict)

    def to_eeprom_data(self):
        """ Create EepromData from the EepromModel. """
        data = []

        id_field = self.__class__.get_id_field()
        id = None if id_field is None else self.__dict__[id_field]

        for (field_name, field_type) in self.__class__.get_fields():
            if field_name in self.__dict__ and field_type.is_writable():
                if isinstance(field_type, CompositeDataType):
                    data.extend(field_type.to_eeprom_data(self.__dict__[field_name], id))
                else:
                    address = field_type.get_address(id)
                    bytes = field_type.to_bytes(self.__dict__[field_name])
                    data.append(EepromData(address, bytes))

        return data

    @classmethod
    def from_eeprom_data(cls, data, id=None, fields=None):
        """ Create an EepromModel from EepromData. """
        cls.check_id(id)

        # Put the data in a dict by address
        data_dict = dict()
        for d in data:
            data_dict[d.address] = d

        field_dict = dict()

        if fields == None:
            # Add data for all fields.
            for (field_name, field_type) in cls.get_fields():
                if isinstance(field_type, CompositeDataType):
                    field_dict[field_name] = field_type.from_data_dict(data_dict, id)
                else:
                    address = field_type.get_address(id)
                    bytes = data_dict[address].bytes
                    field_dict[field_name] = field_type.from_bytes(bytes)
        else:
            # Add data for given fields only.
            class_field_dict = cls.get_field_dict()
            for field_name in fields:
                if field_name not in class_field_dict:
                    raise TypeError("Field %s is unknown for %s" % (field_name, cls.__name__))
                else:
                    field_type = class_field_dict[field_name]
                    if isinstance(field_type, CompositeDataType):
                        field_dict[field_name] = field_type.from_data_dict(data_dict, id)
                    else:
                        address = field_type.get_address(id)
                        bytes = data_dict[address].bytes
                        field_dict[field_name] = field_type.from_bytes(bytes)

        if id is not None:
            field_dict[cls.get_id_field()] = id

        return cls(**field_dict)

    @classmethod
    def get_addresses(cls, id=None, fields=None):
        """ Get the addresses used by this EepromModel. """
        cls.check_id(id)
        addresses = []

        if fields == None:
            # Add addresses for all fields.
            for (_, field_type) in cls.get_fields():
                if isinstance(field_type, CompositeDataType):
                    addresses.extend(field_type.get_addresses(id))
                else:
                    addresses.append(field_type.get_address(id))

        else:
            # Add addresses for given fields only.
            class_field_dict = cls.get_field_dict()

            for field in fields:
                if field not in class_field_dict:
                    raise TypeError("Field %s is unknown for %s" % (field, cls.__name__))
                else:
                    field_type = class_field_dict[field]
                    if isinstance(field_type, CompositeDataType):
                        addresses.extend(field_type.get_addresses(id))
                    else:
                        addresses.append(field_type.get_address(id))

        return addresses


class EepromId(object):
    """ Represents an id in an EepromModel. """

    def __init__(self, max_id, address=None, multiplier=None):
        """ Constructor.

        @param max_id: the static maximum for the id.
        @type max_id: Integer.
        @param address: the EepromAddress where the dynamic maximum for the id is located.
        @type address: EepromAddress.
        @param multiplier: if an address is provided, the multiplier can be used to multiply the
        value located at that address.
        @type multiplier: Integer.
        """
        self.__max_id = max_id
        self.__address = address
        if multiplier is not None and self.__address is None:
            raise TypeError("A multiplier was specified without an address")
        else:
            self.__multiplier = multiplier if multiplier != None else 1

    def get_max_id(self):
        """ Get the static maximum id. """
        return self.__max_id

    def has_address(self):
        """ Check if the EepromId has a dynamic maximum. """
        return self.__address is not None

    def get_address(self):
        """ Get the EepromAddress. """
        return self.__address

    def get_multiplier(self):
        """ Return the multiplier for the Eeprom value (at the defined EepromAddress). """
        return self.__multiplier


class CompositeDataType(object):
    """ Defines a composite data type in an EepromModel, the composite structure contains multiple
    EepromDataTypes and defines a name for each child data type.
    """

    def __init__(self, eeprom_data_types, read_only=False):
        """Create a new composite data type using a list of tuples (name, EepromDataType). """
        self.__eeprom_data_types = eeprom_data_types
        self.__read_only = read_only

    def get_addresses(self, id=None):
        """ Get all EepromDataType addresses in the composite data type. """
        return [t[1].get_address(id) for t in self.__eeprom_data_types]

    def get_name(self):
        """ Get the name of the EepromDataType. To be implemented in the subclass. """
        return "[%s]" % (",".join(["%s(%s)" % (t[0], t[1].get_name())
                                   for t in self.__eeprom_data_types]))

    def from_data_dict(self, data_dict, id=None):
        """ Convert a data_dict (mapping from EepromAddress to EepromData) to a list of fields. """
        out = []

        for (_, field_type) in self.__eeprom_data_types:
            address = field_type.get_address(id)
            bytes = data_dict[address].bytes
            out.append(field_type.from_bytes(bytes))

        return out

    def to_eeprom_data(self, fields, id=None):
        """ Convert a list of field data to a list of EepromData objects. """
        if len(fields) != len(self.__eeprom_data_types):
            raise TypeError("The length of the composite data does not match the type:"
                            "got %s for %s." % (fields, self.get_name()))

        out = []

        for i in range(len(fields)):
            field_type = self.__eeprom_data_types[i][1]
            address = field_type.get_address(id)
            bytes = field_type.to_bytes(fields[i])
            out.append(EepromData(address, bytes))

        return out

    def is_writable(self):
        """ Returns whether the CompositeDataType is writable. """
        return not self.__read_only


class EepromDataType(object):
    """ Defines a data type in an EepromModel, and provides functions to_bytes and from_bytes to
    convert this data type from and to a string of bytes.  Besides these functions, the data type
    also contains the address, or the address generator (in case the model has an id).
    """

    def __init__(self, addr_gen, read_only=False):
        """ Create an instance of an EepromDataType with an address or an address generator.
        The address is a tuple of (bank, offset).
        The address generator is a function that takes an id (integer).
        """
        self.__read_only = read_only
        self.__addr_tuple = None
        self.__addr_func = None

        if isinstance(addr_gen, types.TupleType):
            self.__addr_tuple = addr_gen
        elif isinstance(addr_gen, types.FunctionType):
            args = inspect.getargspec(addr_gen).args
            if len(args) == 1:
                self.__addr_func = addr_gen
            else:
                raise TypeError("addr_gen should be a function that takes an id and returns the "
                                " same tuple.")
        else:
            raise TypeError("addr_gen should be a tuple (bank, address) or a function that takes "
                            "an id and returns the same tuple.")

    def is_writable(self):
        """ Returns whether the EepromDataType is writable. """
        return not self.__read_only

    def check_writable(self):
        """ Raises a TypeError if the EepromDataType is not writable. """
        if self.__read_only:
            raise TypeError("EepromDataType is not writable")

    def get_address(self, id=None):
        """ Calculate the address for this data type. """
        length = self.get_length()

        if id is None:
            if self.__addr_tuple is not None:
                (bank, address) = self.__addr_tuple
            else:
                raise TypeError("EepromDataType expects an id")
        else:
            if self.__addr_func is not None:
                (bank, address) = self.__addr_func(id)
            else:
                raise TypeError("EepromDataType did not expect an id")

        return EepromAddress(bank, address, length)

    def get_name(self):
        """ Get the name of the EepromDataType. To be implemented in the subclass. """
        raise NotImplementedError()

    def from_bytes(self, bytes):
        """ Convert a string of bytes to the desired type. To be implemented in the subclass. """
        raise NotImplementedError()

    def to_bytes(self, field):
        """ Convert the field data to a string of bytes. To be implemented in the subclass. """
        raise NotImplementedError()

    def get_length(self):
        """ Get the length of the data type. """
        raise NotImplementedError()


def remove_tail(byte_str, delimiter='\xff'):
    """ Returns a new string where all instance of the delimiter at the end of the string are
    removed.
    """
    index = byte_str.rfind(delimiter)
    while index > 0:
        byte_str = byte_str[:index]
        index = byte_str.rfind(delimiter)

    if index == -1:
        return byte_str
    else:
        return byte_str[:index]


def append_tail(byte_str, length, delimiter='\xff'):
    """ Returns a new string with the given length by adding instances of the delimiter at the end
    of the string.
    """
    if len(byte_str) < length:
        return str(byte_str) + delimiter * ((length - len(byte_str)) / len(delimiter))
    else:
        return str(byte_str)


class EepromString(EepromDataType):
    """ A string with a given length. """

    def __init__(self, length, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__length = length

    def get_name(self):
        return "String[%d]" % self.__length

    def from_bytes(self, bytes):
        return str(remove_tail(bytes))

    def to_bytes(self, field):
        self.check_writable()
        return append_tail(field, self.__length)

    def get_length(self):
        return self.__length


class EepromByte(EepromDataType):
    """ A byte. """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return "Byte"

    def from_bytes(self, bytes):
        return ord(bytes[0])

    def to_bytes(self, field):
        self.check_writable()
        return str(chr(field))

    def get_length(self):
        return 1


class EepromWord(EepromDataType):
    """ A word (2 bytes, converted to an integer). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return "Word"

    def from_bytes(self, bytes):
        return ord(bytes[1]) * 256 + ord(bytes[0])

    def to_bytes(self, field):
        self.check_writable()
        return "".join([chr(int(field) % 256), chr(int(field) / 256)])

    def get_length(self):
        return 2


class EepromTemp(EepromDataType):
    """ A temperature (1 byte, converted to a float). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return "Temp"

    def from_bytes(self, bytes):
        return float(ord(bytes[0])) / 2 - 32

    def to_bytes(self, field):
        self.check_writable()
        return str(chr(int((float(field) + 32) * 2)))

    def get_length(self):
        return 1


class EepromSignedTemp(EepromDataType):
    """ A signed temperature (1 byte, converted to a float, from -7.5 to +7.5). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return "SignedTemp(-7.5 to 7.5 degrees)"

    def from_bytes(self, bytes):
        value = ord(bytes)
        if value == 255:
            return 0.0
        else:
            multiplier = 1 if value & 128 == 0 else -1
            return multiplier * float(value & 15) / 2.0

    def to_bytes(self, field):
        self.check_writable()
        if field <= -8.0 or field >= 8.0:
            raise ValueError("SignedTemp should be in [-7.5, 7.5], was %f" % field)

        if field == 0.0:
            return str(chr(255))
        else:
            offset = 0 if field > 0 else 128
            value = int(abs(field) * 2)
            return str(chr(offset + value))

    def get_length(self):
        return 1


class EepromTime(EepromDataType):
    """ A time (1 byte, converted into string HH:MM). """

    def __init__(self, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)

    def get_name(self):
        return "Time"

    def from_bytes(self, bytes):
        value = ord(bytes[0])
        hours = value / 6
        minutes = (value % 6) * 10
        return "%02d:%02d" % (hours, minutes)

    def to_bytes(self, field):
        self.check_writable()
        split = [int(x) for x in field.split(":")]
        if len(split) != 2:
            raise ValueError("Time is not in HH:MM format: %s" % field)
        field = (split[0] * 6) + (split[1] / 10)
        return str(chr(field))

    def get_length(self):
        return 1


class EepromCSV(EepromDataType):
    """ A list of bytes with a given length (converted to a string of comma separated integers).
    """

    def __init__(self, length, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__length = length

    def get_name(self):
        return "CSV[%d]" % self.__length

    def from_bytes(self, bytes):
        return ",".join([str(ord(b)) for b in remove_tail(bytes, '\xff')])

    def to_bytes(self, field):
        self.check_writable()
        actions = "" if len(field) == 0 else "".join([chr(int(x)) for x in field.split(",")])
        return append_tail(actions, self.__length, '\xff')

    def get_length(self):
        return self.__length


class EepromActions(EepromDataType):
    """ A list of basic actions with a given length (2 bytes each, converted to a string of comma
    separated integers).
    """

    def __init__(self, length, addr_gen, read_only=False):
        EepromDataType.__init__(self, addr_gen, read_only)
        self.__length = length

    def get_name(self):
        return "Actions[%d]" % self.__length

    def from_bytes(self, bytes):
        return ",".join([str(ord(b)) for b in remove_tail(bytes, '\xff\xff')])

    def to_bytes(self, field):
        self.check_writable()
        actions = "" if len(field) == 0 else "".join([chr(int(x)) for x in field.split(",")])
        return append_tail(actions, 2 * self.__length, '\xff\xff')

    def get_length(self):
        return 2 * self.__length

