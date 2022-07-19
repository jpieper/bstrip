#!/usr/bin/python3

# Copyright 2020-2022 Josh Pieper, jjp@pobox.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import asyncio
import math
import moteus
import time

# How much wire is dispensed for one full revolution of the drive
# wheel.
DRIVE_SCALE_CM = 6.5 * math.pi

PRIME_ADVANCE_CM = 1.0
STRIP_EXTRA_RETRACT_CM = 1.0


class Application:
    def __init__(self, args):
        self.args = args

        qr = moteus.QueryResolution()
        qr.trajectory_complete = moteus.INT8
        self.drive = moteus.Controller(id=1, query_resolution=qr)
        self.cut = moteus.Controller(id=2)

    async def stop(self):
        await self.drive.set_stop()
        await self.cut.set_stop()

    async def initialize(self):
        await self.stop()
        await self.set_wire_start()

    async def debug_delay(self):
        if not self.args.slow:
            return
        await asyncio.sleep(0.5)

    async def set_wire_start(self):
        while True:
            await self.drive.set_rezero(0.0, query=True)

            result = None
            while result is None:
                result = await self.drive.query()

            if abs(result.values[moteus.Register.POSITION]) <= 0.5:
                break

        self.wire_start = result.values[moteus.Register.POSITION]

    async def stop(self):
        await self.drive.set_stop()
        await self.cut.set_stop()

    async def cut_break(self):
        '''Execute a full break with the cutter.  Actuate it all the way, then
        release it all the way.
        '''
        while True:
            result = await self.cut.set_position(
                position=math.nan,
                velocity=2.0,
                maximum_torque=2.0,
                stop_position=0.0,
                feedforward_torque=-1.0,
                query=True)
            if result:
                if result.values[moteus.Register.POSITION] < 0.006:
                    break

        await asyncio.sleep(0.05)

        while True:
            result = await self.cut.set_position(
                position=math.nan,
                velocity=4.0,
                maximum_torque=1.0,
                stop_position=0.12,
                query=True)
            if result and result.values[moteus.Register.POSITION] > 0.11:
                break

        # Now lock this in with no timeout.
        await self.cut.set_position(
            position=math.nan,
            velocity=0.0,
            maximum_torque=1.0,
            watchdog_timeout=math.nan)

    async def cut_strip(self, extra=False):
        '''Engage the cutter to puncture the insulation, but not the wire.
        Leave it there.
        '''

        while True:
            result = await self.cut.set_position(
                position=math.nan,
                velocity=2.0,
                maximum_torque=2.0,
                stop_position=0.008 if not extra else 0.006,
                feedforward_torque=-0.1,
                watchdog_timeout=math.nan,
                query=True)
            if result and result.values[moteus.Register.POSITION] < 0.016:
                break

        # We wait a bit for the insulation to deform.
        await asyncio.sleep(0.1)

        while True:
            result = await self.cut.set_position(
                position=math.nan,
                velocity=4.0,
                maximum_torque=1.0,
                stop_position=0.014,
                feedforward_torque=-0.05,
                watchdog_timeout=math.nan,
                query=True)
            if result and result.values[moteus.Register.POSITION] > 0.008:
                break

        await asyncio.sleep(0.05)

    async def cut_release(self):
        '''Release the cutter into the disengaged position.  Usually from the
        "strip" position.
        '''

        while True:
            result = await self.cut.set_position(
                position=math.nan,
                velocity=4.0,
                maximum_torque=1.0,
                stop_position=0.12,
                watchdog_timeout=math.nan,
                query=True)
            if result and result.values[moteus.Register.POSITION] > 0.11:
                break


    async def drive_rezero(self):
        '''Rezero the drive wheel.  Should be performed from time to time, at
        the start of a cycle is a good time.'''

        pass

    async def drive_advance(self, distance_cm, kp=None, feedforward=None):
        '''Move the drive to the given distance as measured from the "wire
        start".
        '''

        desired_pos = self.wire_start + distance_cm / DRIVE_SCALE_CM

        while True:
            result = await self.drive.set_position(
                position=desired_pos,
                velocity=0.0,
                maximum_torque=2.0,
                velocity_limit=3.0,
                accel_limit=15.0,
                watchdog_timeout=math.nan,
                feedforward_torque=feedforward,
                kp_scale=kp,
                query=True)
            if result is None:
                continue
            error_cm = (result.values[moteus.Register.POSITION] -
                        desired_pos) * DRIVE_SCALE_CM
            if (abs(error_cm) < 0.2 and
                result.values[moteus.Register.TRAJECTORY_COMPLETE]):
                break

        await asyncio.sleep(0.20)

    async def wire(self):
        args = self.args

        if args.prime:
            await self.drive_advance(PRIME_ADVANCE_CM)
            await self.cut_break()

        for n in range(args.count):
            print("CUT NUMBER:", n + 1)
            await self.set_wire_start()

            if args.strip != 0.0:
                await self.drive_advance(args.strip)
                await self.debug_delay()

                await self.cut_strip()
                await self.debug_delay()

                await self.drive_advance(-STRIP_EXTRA_RETRACT_CM, kp=1)
                await self.debug_delay()

                await self.cut_release()
                await self.debug_delay()

            if args.cut != 0.0:
                await self.drive_advance(args.length - args.cut)
                await self.debug_delay()

                await self.cut_strip(extra=True)
                await asyncio.sleep(0.1)

                await self.cut_release()
                await self.debug_delay()

            await self.drive_advance(args.length)
            await self.debug_delay()
            await self.cut_break()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)

    # Things for automated wire production.
    parser.add_argument('-l', '--length', type=float,
                        help='overall length in cm')
    parser.add_argument('-s', '--strip', type=float, default=0.0,
                        help='length of strip (0.0 means no strip)')
    parser.add_argument('-c', '--cut', type=float, default=0.0,
                        help='length of opposite side cut (0.0 means no cut)')
    parser.add_argument('-p', '--prime', action='store_true',
                        help='spool and cut a small amount of wire to begin with')
    parser.add_argument('-n', '--count', type=int, default=1,
                        help='make this many instances')
    parser.add_argument('--slow', action='store_true',
                        help='add debugging delays')

    # Debugging single-action options.
    parser.add_argument('-a', '--action', type=str)

    args = parser.parse_args()

    app = Application(args)

    await app.initialize()

    if args.action:
        if args.action == 'break':
            await app.cut_break()
        elif args.action == 'stop':
            await app.stop()
        elif args.action == 'strip':
            await app.cut_strip()
        elif args.action == 'release':
            await app.cut_release()
        elif args.action.startswith('advance'):
            await app.drive_advance(float(args.action.split('_')[1]))
        elif args.action == 'query':
            print(await app.cut.query())
        else:
            raise RuntimeError(f'Unknown action: {args.action}')
    else:
        await app.wire()

    await app.stop()


if __name__ == '__main__':
    asyncio.run(main())
