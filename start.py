import asyncio
import time

start_time = time.time()
from scripts.utils.handle_dependencies import handle_dependencies
handle_dependencies()

import argparse
from adambot import AdamBot

parser = argparse.ArgumentParser()
# todo: make this more customisable
parser.add_argument("-p", "--prefix", nargs="?", default=None)
parser.add_argument("-t", "--token", nargs="?", default=None)  # can change token on the fly/keep env clean
parser.add_argument("-c", "--connections", nargs="?",
                    default=10)  # DB pool max_size (how many concurrent connections the pool can have)
args = parser.parse_args()

try:
    asyncio.run(AdamBot(start_time, token=args.token, connections=args.connections,
            command_prefix=args.prefix).start_up())
except Exception as e:
    print(e)
    pass  # shush