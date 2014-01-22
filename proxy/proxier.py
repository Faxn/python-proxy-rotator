import threading, collections, sys, socket, os, select, threading, logging
from tempfile import gettempdir
log = logging.getLogger(__name__)

_DEFAULT_TEST_SERVER = 'www.vg.no'

def _test_alive(_socket, server):
    try:
        _socket.connect(server)
        log.debug("%s:%s ALIVE", *server)
    except (socket.timeout, socket.error) as e:
        log.debug("%s:%s DEAD: "+ str(e), *server)
        return False
    return True

def _test_CONNECT(_socket, server, test_server=_DEFAULT_TEST_SERVER):
    try:
        _socket.sendall(bytes("CONNECT %s HTTP/1.0\r\n\r\n" % test_server, "utf-8"))
        ready = select.select([_socket], [], [], 4)
        if ready[0]:
            resp = str(_socket.recv(1), "utf-8")
            while resp.find("\r\n\r\n")==-1:
                tmp = resp
                resp = resp + str(_socket.recv(1), "utf-8")
                if tmp == resp: raise socket.error
            statusline = resp.splitlines()[0].split(" ",2)
            statuscode = int(statusline[1])
            if statuscode != 200:
                log.debug("%s:%s Can't Chain: Code " + str(statuscode) , *server)
                return False
            log.debug("%s:%s supports CONNECT!", *server)
            return True
    except (socket.error, ValueError) as e:
        log.debug("%s:%s Can't Chain: "+ str(e), *server)
    return False

class ProxyManager():
    
    def __init__(self, check_for_tmp):
        self.lock = threading.Lock()
        self.killer = threading.Lock()
        self.http_proxies = collections.deque()
        self.https_proxies = collections.deque()
        self.dead = collections.deque()
        self._load_proxies(check_for_tmp)

    def _print_progress(self, fraction):
        if log.getEffectiveLevel() <= logging.DEBUG: #debug messages mess with the progress bar
            return
        size = 50
        progress = int(round(size * fraction))
        string = "="*progress+" "*int(size-progress)
        
        if fraction == 1: sys.stdout.write("\r[%s] Done!       \n" % string)
        else: sys.stdout.write("\r[%s] Loading..." % string)
        sys.stdout.flush()
    
    def _load_proxies(self, check_for_tmp=True):
        if check_for_tmp and os.path.exists(os.path.join(gettempdir(),'py_http_proxies.txt')):
            log.info('Loading proxies from local tmp...')
            file = open(os.path.join(gettempdir(),'py_http_proxies.txt'),'r').readlines()
            for entry in file:
                entry = ( entry.split(":")[0], int(entry.split(":")[1]) )
                self.http_proxies.append( entry )
            
            file = open(os.path.join(gettempdir(),'py_https_proxies.txt'),'r').readlines()
            for entry in file:
                entry = ( entry.split(":")[0], int(entry.split(":")[1]) )
                self.https_proxies.append( entry )
        else:
            log.info('Loading proxies from proxylist.txt ...')
            
            fresh_proxies = open(os.path.join(os.getcwd(),'proxy/proxylist.txt'),'r').readlines()
            self.add_proxies(fresh_proxies)
        
            save = open(os.path.join(gettempdir(),'py_http_proxies.txt'),'w')
            for p in self.http_proxies:
                save.write('%s:%d\n' % p)
            save.close()
        
            save = open(os.path.join(gettempdir(),'py_https_proxies.txt'),'w')
            for p in self.https_proxies:
                save.write('%s:%d\n' % p)
            save.close()
        
        log.info('%d HTTPS proxies with chain support', len(self.https_proxies))
        log.info('%d HTTP proxies', len(self.http_proxies))
        
    def add_proxies(self, fresh_proxies, threads=10):
        sema = threading.BoundedSemaphore(threads)
        children = [None] * len(fresh_proxies)
        for i,entry in enumerate(fresh_proxies):
            if self.killer.locked(): break
            proxy_addr = ( entry.split(":")[0], int(entry.split(":")[1]) )
            children[i] = threading.Thread(target=self.add_proxy, args=(proxy_addr, sema))
            children[i].start()
        for index, child in enumerate(children):
            self._print_progress( (index+1)/float(len(fresh_proxies)) )
            child.join()
    
    def add_proxy(self, proxy_addr, _lock):
        with _lock:
            alive,chaining = self._check_proxy( proxy_addr )
            if alive:
                if chaining: self.https_proxies.append( proxy_addr )
                else: self.http_proxies.append( proxy_addr )
            else: self.dead.append(proxy_addr)
        
    
    def _check_proxy(self, proxy_addr):
        _socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        _socket.settimeout(3)
        
        alive = _test_alive(_socket, proxy_addr)
        if alive:
            chaining = _test_CONNECT(_socket, proxy_addr)
        else:
            chaining = False

        _socket.close()
        return (alive, chaining)
    
    def get_proxy(self):
        self.lock.acquire()
        
        random_proxy = self.http_proxies[0]
        self.http_proxies.rotate(1)
        
        self.lock.release()
        return random_proxy
    
    def get_sslproxy(self, count=1):
        self.lock.acquire()
        
        if count <= 0: return [ ]
        if count > len(self.https_proxies): count = len(self.https_proxies)
        
        random_proxy = [self.https_proxies.pop() for i in range(count)]
        self.https_proxies.extendleft(random_proxy)
        
        
        self.lock.release()
        return random_proxy
    
    def remove_proxy(self, proxy):
        self.lock.acquire()
        for i,p in enumerate(self.https_proxies):
            if proxy[0] == p[0]: self.https_proxies.remove(p)
        for i,p in enumerate(self.http_proxies):
            if proxy[0] == p[0]: self.http_proxies.remove(p)
        self.lock.release()
    
    def terminate(self):
        self.killer.acquire()
