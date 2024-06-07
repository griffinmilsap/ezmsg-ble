import typing
import asyncio
import typing

import ezmsg.core as ez

class Args:
    topic: str
    device: str
    server: bool

def server(args: Args) -> None:

    from ezmsg.util.debuglog import DebugLog
    from ezmsg.ble.server import BLETopicServer, BLETopicServerSettings
    
    class Counter(ez.Unit):

        OUTPUT_NUMBER_BYTES = ez.OutputStream(bytes)

        INPUT_NUMBER_BYTES = ez.InputStream(bytes)
        OUTPUT_NUMBER = ez.OutputStream(int)

        @ez.publisher(OUTPUT_NUMBER_BYTES)
        async def count(self) -> typing.AsyncGenerator:
            current_value = 0
            while True:
                await asyncio.sleep(1.0)
                yield self.OUTPUT_NUMBER_BYTES, current_value.to_bytes(4, byteorder = 'big')
                current_value += 1

        @ez.subscriber(INPUT_NUMBER_BYTES)
        @ez.publisher(OUTPUT_NUMBER)
        async def translate_numbers(self, msg: bytes) -> typing.AsyncGenerator:
            yield self.OUTPUT_NUMBER, int.from_bytes(msg, byteorder = 'big')
                

    log = DebugLog()
    counter = Counter()

    topic_server = BLETopicServer(
        BLETopicServerSettings(
            topic = args.topic
        )
    )

    ez.run(
        TOPIC_SERVER = topic_server,
        LOG = log,
        COUNTER = counter,

        connections = (
            (counter.OUTPUT_NUMBER_BYTES, topic_server.BROADCAST),
            (topic_server.INCOMING_UPDATE, counter.INPUT_NUMBER_BYTES),
            (counter.OUTPUT_NUMBER, log.INPUT)
        )
    )

def client(args: Args) -> None:

    from ezmsg.ble.client import BLETopicClient, BLETopicClientSettings
    from ezmsg.util.debuglog import DebugLog

    class Loopback(ez.Unit):

        INPUT = ez.InputStream(bytes)
        OUTPUT = ez.OutputStream(bytes)
        OUTPUT_NUMBER = ez.OutputStream(int)

        @ez.subscriber(INPUT)
        @ez.publisher(OUTPUT)
        @ez.publisher(OUTPUT_NUMBER)
        async def on_msg(self, msg: bytes) -> typing.AsyncGenerator:
            yield self.OUTPUT, msg
            yield self.OUTPUT_NUMBER, int.from_bytes(msg, 'big')

    topic_client = BLETopicClient(
        BLETopicClientSettings(
            device = args.device,
            topic = args.topic
        )
    )

    log = DebugLog()
    loopback = Loopback()

    ez.run(
        LOG = log,
        CLIENT = topic_client,
        LOOPBACK = loopback,

        connections = (
            (topic_client.INCOMING_BROADCAST, loopback.INPUT),
            (loopback.OUTPUT, topic_client.UPDATE),
            (loopback.OUTPUT_NUMBER, log.INPUT)
        )
    )


if __name__ == '__main__':
    
    import argparse

    parser = argparse.ArgumentParser(description = 'BLE topic loopback example')

    parser.add_argument(
        'topic',
        help = 'topic name'
    )

    parser.add_argument(
        '--device',
        help = 'device to search for/connect to (client only)',
        default = ''
    )

    parser.add_argument(
        '--server', 
        action = 'store_true',
        help = 'run topic server'
    )

    args = parser.parse_args(namespace = Args)

    main = server if args.server else client
    main(args)
