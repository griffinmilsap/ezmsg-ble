
import json
import asyncio
import typing
import uuid

from bleak import (
    BleakClient,
    BleakScanner,
    BleakGATTCharacteristic
)

import ezmsg.core as ez

from ezmsg.sigproc.sampler import SampleTriggerMessage
from ezmsg.util.messagecodec import MessageEncoder, MessageDecoder

from .topic_server import gen_characteristic_uuid

class BLETopicClientSettings(ez.Settings):
    topic: str
    connect_retries: int = 3

class BLETopicClientState(ez.State):
    conn: typing.Optional[BleakClient] = None
    characteristic_uuid: typing.Optional[uuid.UUID] = None
    queue: asyncio.Queue[str]

class BLETopicClient(ez.Unit):
    SETTINGS: BLETopicClientSettings
    STATE: BLETopicClientState

    INCOMING_BROADCAST = ez.OutputStream(typing.Any)
    UPDATE = ez.InputStream(typing.Any)

    async def initialize(self) -> None:
        self.STATE.queue = asyncio.Queue()

    @ez.task
    async def handle_connection(self) -> None:
        while True:
            name = self.SETTINGS.topic
            ez.logger.info(f"Looking for BLE device/server: {name}")
            device = None
            while device is None:
                # FIXME: Constantly scanning for a device might degrade bluetooth performance
                device = await BleakScanner.find_device_by_name(name = name, timeout = 20.0)

            ez.logger.info(f"Attempting connection: {device=}")

            try:

                disconnected = asyncio.Event()
                def on_disconnect(_: BleakClient) -> None:
                    disconnected.set()

                self.STATE.conn = BleakClient(
                    device, 
                    timeout = 20, # sec
                    disconnected_callback = on_disconnect
                )

                for retry in range(self.SETTINGS.connect_retries):
                    try:
                        await self.STATE.conn.connect()
                        break
                    except asyncio.TimeoutError:
                        if retry + 1 == self.SETTINGS.connect_retries:
                            ez.logger.warning(f"Failed to connect to {device}")
                            break
                        ez.logger.warning(f"Timed out while connecting to {device}")
                        ez.logger.info(f"{device=}")

                if not self.STATE.conn.is_connected:
                    continue

                ez.logger.info(f"Connected to {device}")
                
                self.STATE.characteristic_uuid = gen_characteristic_uuid(self.SETTINGS.topic)
                
                async def callback_handler(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
                    print(characteristic.uuid, str(self.STATE.characteristic_uuid))
                    if characteristic.uuid == str(self.STATE.characteristic_uuid):
                        await self.STATE.queue.put(bytes(data).decode())

                await self.STATE.conn.start_notify(
                    self.STATE.characteristic_uuid, 
                    callback_handler
                )

                await disconnected.wait()
                ez.logger.info(f"Disconnected from {device}")
                
            finally:
                if self.STATE.conn and self.STATE.characteristic_uuid and self.STATE.conn.is_connected:
                    await self.STATE.conn.stop_notify(
                        self.STATE.characteristic_uuid
                    )
                    await self.STATE.conn.disconnect()
                self.STATE.conn = None
                self.STATE.characteristic_uuid = None


    @ez.publisher(INCOMING_BROADCAST)
    async def pub_stims(self) -> typing.AsyncGenerator:
        while True:
            data = await self.STATE.queue.get()
            msg = json.loads(data, cls = MessageDecoder)
            yield self.INCOMING_BROADCAST, msg


    @ez.subscriber(UPDATE)
    async def on_trig(self, msg: SampleTriggerMessage) -> None:
        if self.STATE.conn is None or self.STATE.characteristic_uuid is None:
            return
        
        msg_data = json.dumps(msg, cls = MessageEncoder)
        await self.STATE.conn.write_gatt_char(
            self.STATE.characteristic_uuid,
            data = bytearray(msg_data.encode()),
            response = False
        )
