import typing
import asyncio

import ezmsg.core as ez

from ezmsg.util.debuglog import DebugLog

from msg import CountMessage


class Args:
    topic: str
    device: str
    server: bool


def server(args: Args) -> None:

    from ezmsg.ble.server import BLETopicServer, BLETopicServerSettings
    
    class Counter(ez.Unit):

        OUTPUT_COUNT = ez.OutputStream(CountMessage)

        @ez.publisher(OUTPUT_COUNT)
        async def count(self) -> typing.AsyncGenerator:
            current_value = 0
            while True:
                await asyncio.sleep(1.0)
                yield self.OUTPUT_COUNT, CountMessage.create(
                    id = 0xEF,
                    count = current_value,
                    percent = 0.65,
                    value = 8.598
                )
                current_value += 1
                

    log = DebugLog()
    counter = Counter()

    topic_server = BLETopicServer(
        BLETopicServerSettings(
            topic = args.topic,
            output_type = CountMessage # Define deserialization type by specifying output_type
        )
    )

    ez.run(
        TOPIC_SERVER = topic_server,
        LOG = log,
        COUNTER = counter,

        connections = (
            (counter.OUTPUT_COUNT, topic_server.BROADCAST),
            (topic_server.INCOMING_UPDATE, log.INPUT)
        )
    )

def client(args: Args) -> None:

    from ezmsg.ble.client import BLETopicClient, BLETopicClientSettings

    topic_client = BLETopicClient(
        BLETopicClientSettings(
            device = args.device,
            topic = args.topic,
            output_type = CountMessage, # Comment me to see bytes in debug log
        )
    )

    log = DebugLog()

    ez.run(
        LOG = log,
        CLIENT = topic_client,

        connections = (
            (topic_client.INCOMING_BROADCAST, topic_client.UPDATE),
            (topic_client.INCOMING_BROADCAST, log.INPUT)
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
