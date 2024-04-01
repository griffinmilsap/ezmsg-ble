# ezmsg.ble [EXPERIMENTAL]

Bluetooth low-energy GATT client/server units for ezmsg. 

## Dependencies
* `ezmsg`
* `bleak` (for the client)
* `bless` (for the server)

## Setup (Development)
1. Install `ezmsg` either using `pip install ezmsg` or set up the repo for development as described in the `ezmsg` readme.
2. `cd` to this directory (`ezmsg-ble`) and run `pip install -e .`

## Notes
As of the current implementation, this module provides two units: `BLETopicClient` and `BLETopicServer`

`BLETopicClient` relies on [`bleak`](https://github.com/hbldh/bleak) which is a pretty mature cross-platform BLE client module at this point, but `BLETopicServer` relies on [`bless`](https://github.com/kevincar/bless) which provides server capabilities, but is MUCH less mature, evolving rapidly, and is very experimental.  As such, this module should be treated as pre-release; very experimental, and may not work on all combinations of operating systems, or with some bluetooth hardware.

__This module has been developed/tested with a Raspberry Pi 4 running as the server and a MacOS M1 laptop running as the client.__ It didn't work with roles reversed; there's probably some MacOS-specific bluetooth-fu that's required to get this up and running.

There are a few important concepts about BLE Generic Attribute profiles (GATT) to be aware of.  The "adapter" is at the top-level of the heirarchy, which is the actual bluetooth device hardware hosting the GATT profile.  It has a classic address (`XX:XX:XX:XX:XX:XX`) as well as a low-energy address which takes the form of a 128-bit UUID (`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`) which is defined by the hardware/operating system.  The device can host a number of GATT "services", which are given customized UUIDs.  Each GATT service can have a number of characteristics which are readable/writeable "registers" that any client can also subscribe to notifications and indications (notifications with an acknowledgement) on.  

`BLETopicServer` currently defines a single service containing a single characteristic that broadcasts indications to at least 1 `BLETopicClient`.  Messages sent to `BLETopicServer`'s `BROADCAST` `InputStream` will update the value of the characteristic and issue an `indicate` to all connected `BLETopicClient`s.  When a `BLETopicClient` receives an `indicate`, it will recieve/deserialize the new value of the characteristic and publish that message on its `INCOMING_BROADCAST` `OutputStream`. Any message received by the `BLETopicClient`'s `UPDATE` `InputStream` will result in the client writing/updating the serialized message to the `BLETopicServer` and the server will publish this message on the server-side under its `INCOMING_UPDATE` `OutputStream`.  

Serialization/deserialization is currently handled via `ezmsg`'s custom JSON serialization codec, available in `ezmsg.util.messagecodec`.  This was done to enable clients implemented in different languages on different platforms the ability to parse/reply to messages using friendly message encoding.  It should be noted, however, that ble's bandwidth is quite limited and JSON-encoded messages are quite large compared to binary formats.  Your mileage may vary.


### `BLETopicServer`
As currently written, each `BLETopicServer` unit creates one of `bless`'s `BlessServer` instances.  `BlessServer` appears to create an "alias" for your bluetooth device to name it whatever you want your device to appear as.  Importantly, if you try to create two `BlessServer`s, your bluetooth device will receive two aliases, and will be discoverable under several names.  It might be best to only have one `BlessServer` per bluetooth device; which means running only one `BLETopicServer` (as currently written) per-host.  It is much more common/user friendly to scan for devices by name/alias rather than requiring a client to directly-connect to a device by address.  Currently this device name is set to the `topic` string itself.  Running two `BLETopicServer`s currently results in weird behavior where the device receives two aliases, and both characteristics appear to have the same UUID (which is quite unexpected).  This is probably a bug in `bless` right now.

### `BLETopicClient`
As written, `BLETopicClient`s will search for any bluetooth device that matches the `topic` setting, connect to it, and look for the corresponding topic/characteristic defined by that device and subscribe to notifications on that characteristic.  Do note that the current implementation will scan for the device forever until it is found, then connect to it and handle the connection until disconnection, then resume scanning for the device forever.  Scanning for devices tends to degrade bluetooth performance causing latency and lag for other services using bluetooth on the same device.  

## Future Work
This module is currently much more limited in scope than it could be due to time constraints.  As written, this allows one pair of devices to communicate messages over _one single characteristic_ in _one service_ while _completely monopolizing the device name on the server side_.  __In the future, this module will likely deprecate `BLETopicServer` and `BLETopicClient`__ in favor of a single `BLEServer` `Collection` that creates multiple `BLEChannel` `Unit`s for individual topics on the server side.  `BLEServer` should alias the bluetooth adapter to something like `ezmsg-ble: [HOSTNAME]` and provide a root `ezmsg-ble` service under which all `BLEChannel` characteristics are indexed.  A root characteristic in this service should provide names for all the associated channel characteristics, enabling the client to connect to arbitrary `BLEChannels` on any device running `ezmsg-ble`.

It may be beneficial to rewrite the main loop of the client to wait for a "connect" message containing a device name to scan for, or an address to directly connect to; and attach this to some UI component so that users have the ability to manually initiate the connection, after an initial auto-connect once on startup.

It would be advisable to wait for a more mature release of `bless` before putting significant effort into this more advanced implementation/rewrite of `ezmsg-ble`.
