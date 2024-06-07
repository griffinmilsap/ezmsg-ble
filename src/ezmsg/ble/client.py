
import asyncio
import typing
import uuid

from bleak import (
    BleakClient,
    BleakScanner,
    BleakGATTCharacteristic
)

import ezmsg.core as ez

from .server import gen_characteristic_uuid, MIN_MTU

class BLETopicClientSettings(ez.Settings):
    device: str
    topic: str
    connect_retries: int = 3

class BLETopicClientState(ez.State):
    conn: typing.Optional[BleakClient] = None
    characteristic_uuid: typing.Optional[uuid.UUID] = None
    queue: asyncio.Queue[bytes]

class BLETopicClient(ez.Unit):
    SETTINGS: BLETopicClientSettings
    STATE: BLETopicClientState

    INCOMING_BROADCAST = ez.OutputStream(bytes)
    UPDATE = ez.InputStream(bytes)

    async def initialize(self) -> None:
        self.STATE.queue = asyncio.Queue()

    @ez.task
    async def handle_connection(self) -> None:
        while True:
            name = self.SETTINGS.device
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
                    if characteristic.uuid == str(self.STATE.characteristic_uuid):
                        await self.STATE.queue.put(bytes(data))

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
    async def incoming(self) -> typing.AsyncGenerator:
        while True:
            data = await self.STATE.queue.get()
            yield self.INCOMING_BROADCAST, data


    @ez.subscriber(UPDATE)
    async def update(self, msg: bytes) -> None:
        if self.STATE.conn is None or self.STATE.characteristic_uuid is None:
            return
        
        if not isinstance(msg, bytes):
            ez.logger.error(f'Cannot write non-bytes object of type: {type(msg)=}')
            return

        if len(msg) > MIN_MTU:
            ez.logger.warning(f'Notification larger than {MIN_MTU=}; may truncate')
        
        await self.STATE.conn.write_gatt_char(
            self.STATE.characteristic_uuid,
            data = bytearray(msg),
            response = False
        )
