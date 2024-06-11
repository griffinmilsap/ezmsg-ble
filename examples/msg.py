# BLETopicServer serves a GATT characteristic, which has a default 
# Maximum Transmissible Unit (MTU) of 23 bytes.  This is pretty small
# This typically means you will need to implement a binary protocol
# for your messages.  This pattern can help you simplify your code.

# BLETopicServer/Client both check if your message type has to/from_bytes, and
# handles message (de)serialization without the need for an intermediary unit

import typing
import struct

from dataclasses import dataclass

@dataclass
class Serializable(typing.Protocol):

    def __post_init__(self) -> None:
        for field, value in self.kwargs_from_bytes(self.to_bytes()).items():
            setattr(self, field, value)

    def to_bytes(self) -> bytes:
        ...

    @classmethod
    def kwargs_from_bytes(cls, data: bytes) -> typing.Dict[str, typing.Any]:
        ...
    
    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(**cls.kwargs_from_bytes(data))
    

@dataclass
class CountMessage(Serializable):

    # Underlying data representation in proper order
    # See https://docs.python.org/3/library/struct.html
    # Un-hinted class attributes are not treated as fields by dataclass
    # Struct corresponds to field order here
    STRUCT = struct.Struct('<hBBf')

    id: int # int16
    count: int # uint8
    percent: float # uint8
    value: float # float32
        
    # Serialization and deserialization    
    def to_bytes(self) -> bytes:
        return self.STRUCT.pack(
            self.id, 
            self.count % 0xFF, 
            max(min(int(self.percent * 0xFF), 0xFF - 1), 0),
            self.value
        )
    
    @classmethod
    def kwargs_from_bytes(cls, data: bytes) -> typing.Dict[str, typing.Any]:
        id, count, percent, value = cls.STRUCT.unpack(data)
        return dict(
            id = id,
            count = count, 
            percent = percent / 0xFF, 
            value = value
        )

    
if __name__ == '__main__':

    requested_params = dict(id = 0xAD, count = 56, percent = 0.25, value = 3.14159265358)
    msg = CountMessage(**requested_params)

    print('Note that requested params does not exactly match created object due to underlying data represenatations')
    print(f'{requested_params=}')
    print(msg)

    print('Also note that pack/unpack maintains equivalence')
    bytes_repr = msg.to_bytes()
    print(f'{len(bytes_repr)=} bytes, {bytes_repr}')
    print(msg.from_bytes(msg.to_bytes()))
