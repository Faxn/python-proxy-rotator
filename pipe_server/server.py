#!/usr/bin/env python
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from .handler import ProxiedRequestHandler
from proxy.proxier import ProxyManager
import logging
log = logging.getLogger("pipe_server.server")
try:
	from .ca_generator import CertificateAuthority
except ImportError:
	log.warn("WARNING: Could not Initate CA. SSL Tunnels might not be secure.")
	CertificateAuthority = lambda : None

class PipeServer(HTTPServer):
    def __init__(self, server_address=('', 8080), try_local_proxylist=True, chainlength=0):
        HTTPServer.__init__(self, 
                        server_address, 
                        ProxiedRequestHandler,
                    )
        self.ca = CertificateAuthority()
        self.proxy_fetcher = ProxyManager(try_local_proxylist)
        self.CHAIN = chainlength


class ThreadedPipeServer(ThreadingMixIn, PipeServer):
    def stop_proxy(self):
        self.proxy_fetcher.terminate()
    
    def terminate(self):
        self.stop_proxy() # stop loading proxies
        self.socket.close()
    
    def setchainlength(self,length):
        self.CHAIN = length
