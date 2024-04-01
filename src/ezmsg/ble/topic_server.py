import json
import uuid
import typing
import hashlib
import asyncio
import typing

from bless import ( 
    BlessServer, # type: ignore
    BlessGATTCharacteristic,# type: ignore
    GATTCharacteristicProperties, # type: ignore
    GATTAttributePermissions # type: ignore
)

import ezmsg.core as ez

from ezmsg.util.messagecodec import MessageEncoder, MessageDecoder

EZBT = 'ezbt'
EZBT_ID = int.from_bytes(EZBT.encode(), 'big')

def _ble_uuid(topic: str, type_bytes: bytes) -> uuid.UUID:
    topic_bytes = hashlib.sha1(topic.encode()).digest()[-10:]
    return uuid.UUID(bytes = EZBT.encode() + type_bytes + topic_bytes)

def gen_service_uuid(topic: str) -> uuid.UUID:
    return _ble_uuid(topic, type_bytes = b'\x00\x00')

def gen_characteristic_uuid(topic: str) -> uuid.UUID:
    return _ble_uuid(topic, type_bytes = b'\x00\x01')


class BLETopicServerSettings(ez.Settings):
    topic: str

class BLETopicServerState(ez.State):
    server: BlessServer
    incoming_queue: asyncio.Queue
    service_uuid: uuid.UUID
    characteristic_uuid: uuid.UUID
    characteristic: typing.Optional[BlessGATTCharacteristic]

class BLETopicServer(ez.Unit):
    SETTINGS: BLETopicServerSettings
    STATE: BLETopicServerState

    BROADCAST = ez.InputStream(typing.Any)
    INCOMING_UPDATE = ez.OutputStream(typing.Any)

    async def initialize(self) -> None:

        self.STATE.incoming_queue = asyncio.Queue()

        self.STATE.server = BlessServer(
            name = self.SETTINGS.topic,
            loop = asyncio.get_running_loop()
        )

        self.STATE.server.read_request_func = self.read_request
        self.STATE.server.write_request_func = self.write_request

        self.STATE.service_uuid = gen_service_uuid(self.SETTINGS.topic)
        self.STATE.characteristic_uuid = gen_characteristic_uuid(self.SETTINGS.topic)
        await self.STATE.server.add_new_service(str(self.STATE.service_uuid))

        # This characteristic is used to indicate 
        # to clients //when// and to show //what// stimuli
        await self.STATE.server.add_new_characteristic(
            service_uuid = str(self.STATE.service_uuid), 
            char_uuid = str(self.STATE.characteristic_uuid), 
            properties = (
                GATTCharacteristicProperties.read |
                GATTCharacteristicProperties.write |
                GATTCharacteristicProperties.write_without_response |
                GATTCharacteristicProperties.indicate
            ), 
            value = None, 
            permissions = (
                GATTAttributePermissions.readable |
                GATTAttributePermissions.writeable
            ),
        )

        self.STATE.characteristic = self.STATE.server.get_characteristic(str(self.STATE.characteristic_uuid))

        await self.STATE.server.start()

        ez.logger.info(f'Advertising BLE device/server: {self.SETTINGS.topic}')

    def read_request(self, characteristic: BlessGATTCharacteristic, **kwargs) -> bytearray:
        return characteristic.value

    def write_request(self, characteristic: BlessGATTCharacteristic, value: typing.Any, **kwargs):
        characteristic.value = value
        msg = json.loads(value, cls = MessageDecoder)
        self.STATE.incoming_queue.put_nowait(msg)

    async def shutdown(self) -> None:
        await self.STATE.server.stop()

    @ez.publisher(INCOMING_UPDATE)
    async def pub_triggers(self) -> typing.AsyncGenerator:
        while True:
            msg = await self.STATE.incoming_queue.get()
            yield self.INCOMING_UPDATE, msg

    @ez.subscriber(BROADCAST)
    async def on_stim(self, msg: typing.Any) -> None:
        if self.STATE.characteristic is not None:
            msg_data = json.dumps(msg, cls = MessageEncoder)
            self.STATE.characteristic.value = bytearray(msg_data.encode())
            self.STATE.server.update_value(
                str(self.STATE.service_uuid), 
                str(self.STATE.characteristic_uuid)
            )
