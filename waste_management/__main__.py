import sys
import argparse

from . import WMClient

# create parser for arguments
parser = argparse.ArgumentParser(
    usage="python -m petsafe email pasword"
)
parser.add_argument("email", help="account email address")
parser.add_argument("password", help="account password")

# if no arguments specified, show help
if len(sys.argv) < 3:
    parser.print_help()
    sys.exit(1)

# parse for arguments
args = parser.parse_args()

client = WMClient(args.email, args.password)
client.authenticate()
client.okta_authorize()

accounts = client.get_accounts()

for account in accounts:
    print(account.name)
    services = client.get_services(account.id)

    for svc in services:
        print(svc.name)
        print(client.get_service_pickup(account.id, svc.id))