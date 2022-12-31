import asyncio
import sys
import argparse

from . import WMClient

# create parser for arguments
parser = argparse.ArgumentParser(usage="python -m petsafe email pasword")
parser.add_argument("email", help="account email address")
parser.add_argument("password", help="account password")

# if no arguments specified, show help
if len(sys.argv) < 3:
    parser.print_help()
    sys.exit(1)

# parse for arguments
args = parser.parse_args()


async def run_async():
    client = WMClient(args.email, args.password)
    await client.async_authenticate()
    await client.async_okta_authorize()

    accounts = await client.async_get_accounts()

    for account in accounts:
        print(account.name)
        services = await client.async_get_services(account.id)

        for svc in services:
            print(svc.name)
            print(await client.async_get_service_pickup(account.id, svc.id))


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(run_async())
loop.close()
