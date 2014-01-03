import argparse, sys, threading, cmd
from pipe_server.server import ThreadedPipeServer

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--force_proxy_refresh', action='store_true', help="force the program to reverify the proxies ")
parser.add_argument('-n', '--chainlength', default=1, help="number of servers to bounce through")
parser.add_argument('-D', '--debug', action='store_true', help="debug output")
args = parser.parse_args()

proxy = ThreadedPipeServer(
            try_local_proxylist = False if args.force_proxy_refresh else True,
            chainlength = args.chainlength,
            DEBUG = args.debug
        )
try:
    print "Server is running."
    proxy.serve_forever()
    print 'visible?'
except KeyboardInterrupt:
    sys.stdout.write("\nServer is shuting down. Please wait...")
    proxy.terminate()
    sys.stdout.write(" Done!\n")
    sys.stdout.flush()
