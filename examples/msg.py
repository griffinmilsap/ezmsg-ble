# BLETopicServer serves a GATT characteristic, which has a default 
# Maximum Transmissible Unit (MTU) of 23 bytes.  This is pretty small
# This typically means you will need to implement a binary protocol
# for your messages.  This pattern can help you simplify your code.

# BLETopicServer/Client both check if your message type has to/from_bytes, and
# handles message (de)serialization without the need for an intermediary unit

import struct

from dataclasses import dataclass, asdict

UINT8_MAX = (2 ** 8) - 1

@dataclass
class CountMessage:

    # Underlying data representation in proper order
    # See https://docs.python.org/3/library/struct.html
    # Un-hinted class attributes are not treated as fields by dataclass
    # Struct corresponds to field order here
    STRUCT = struct.Struct('<hBBf')

    # Document underlying data representation in variable name
    id_int16: int = 0
    count_uint8: int = 0
    percent_uint8: int = 0
    value_float32: float = 0

    # Properties to get friendly values
    @property
    def id(self) -> int:
        return self.id_int16

    @property
    def count(self)-> int:
        return self.count_uint8

    @property
    def percent(self) -> float:
        return self.percent_uint8 / UINT8_MAX
    
    @property
    def value(self) -> float:
        return self.value_float32

    # Serialization and deserialization    
    def to_bytes(self) -> bytes:
        return self.STRUCT.pack(*asdict(self).values())

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(*cls.STRUCT.unpack(data))

    # A user friendly constructor
    @classmethod
    def create(cls, id: int, count: int, percent: float, value: float):
        """
        Create a CountMessage with friendlier units

        Parameters:
        id (int): id for count message [-32768, 32767]
        count (int): current count value [0, 255]
        percent (float): a floating point percentage - [0.0 -> 1.0]
            NOTE: represented internally as a uint8; not all values can be accurately represented
        value (float): an example float32; again not all Python float (64 bit) values can be accurately represented

        Returns:
        A properly calculated/validated CountMessage instance

        Notes:
        This method is a class method, meaning it can be called on the class itself rather than an instance.
        """

        return cls.from_bytes(cls.STRUCT.pack(id, count % UINT8_MAX, int(percent * UINT8_MAX), value))
    
    # Friendly representation
    def __repr__(self) -> str:
        return f'CountMessage(id={self.id}, count={self.count}, percent={self.percent}, value={self.value})'
    
if __name__ == '__main__':

    requested_params = dict(id = 0xAD, count = 56, percent = 0.25, value = 3.14159265358)
    msg = CountMessage.create(**requested_params)

    print('Note that requested params does not exactly match created object due to underlying data represenatations')
    print(f'{requested_params=}')
    print(msg)

    print('Also note that pack/unpack maintains equivalence')
    bytes_repr = msg.to_bytes()
    print(f'{len(bytes_repr)=} bytes, {bytes_repr}')
    print(msg.from_bytes(msg.to_bytes()))
