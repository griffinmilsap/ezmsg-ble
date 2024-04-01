import typing
import asyncio
import typing

import ezmsg.core as ez

def server(topic_name: str) -> None:

    from ezmsg.util.debuglog import DebugLog
    from ezmsg.ble.server import BLETopicServer, BLETopicServerSettings
    
    class Counter(ez.Unit):

        OUTPUT_NUMBER = ez.OutputStream(int)

        @ez.publisher(OUTPUT_NUMBER)
        async def pub_numbers(self) -> typing.AsyncGenerator:
            current_value = 0
            while True:
                await asyncio.sleep(1.0)
                yield self.OUTPUT_NUMBER, current_value
                current_value += 1

    log = DebugLog()
    counter = Counter()

    topic_server = BLETopicServer(
        BLETopicServerSettings(
            topic = topic_name
        )
    )

    ez.run(
        TOPIC_SERVER = topic_server,
        LOG = log,
        COUNTER = counter,

        connections = (
            (counter.OUTPUT_NUMBER, topic_server.BROADCAST),
            (topic_server.INCOMING_UPDATE, log.INPUT),
        )
    )

def client(topic_name: str) -> None:

    from ezmsg.ble.client import BLETopicClient, BLETopicClientSettings

    class Loopback(ez.Unit):

        INPUT = ez.InputStream(typing.Any)
        OUTPUT = ez.OutputStream(typing.Any)

        @ez.subscriber(INPUT)
        @ez.publisher(OUTPUT)
        async def on_msg(self, msg: typing.Any) -> typing.AsyncGenerator:
            yield self.OUTPUT, msg

    topic_client = BLETopicClient(
        BLETopicClientSettings(
            topic = topic_name
        )
    )

    loopback = Loopback()

    ez.run(
        CLIENT = topic_client,
        LOOPBACK = loopback,

        connections = (
            (topic_client.INCOMING_BROADCAST, loopback.INPUT),
            (loopback.OUTPUT, topic_client.UPDATE)
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
        '--server', 
        action = 'store_true',
        help = 'run topic server'
    )

    class Args:
        topic: str
        server: bool

    args = parser.parse_args(namespace = Args)

    main = server if args.server else client
    main(args.topic)
