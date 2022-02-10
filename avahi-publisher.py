import io
import os
import socket
import avahi
import dbus
import threading
import queue
import socketserver
import dns.query
import dns.zone
import dns.flags
import dns.message
import dns.name
import dns.exception
import dns.rdataclass
import dns.rdatatype
from time import sleep
from typing import cast

DEBUG          = os.environ.get('DEBUG', None)
DNS_SERVER     = os.environ['DNS_SERVER']
DOMAINS        = os.environ['DOMAINS'].split(' ')
LISTEN_ADDRESS = os.environ.get('LISTEN_ADDRESS', '127.0.0.1')
LISTEN_PORT    = int(os.environ.get('LISTEN_PORT', 53535))
INTERVAL       = int(os.environ.get('INTERVAL', 60))

DEFAULT_TTL = 5

avahi_daemon = None
serials      = dict()
avahi_groups = dict()
q            = queue.Queue()


class AvahiDaemon:
    def __init__(self):
        self.sysbus = dbus.SystemBus()
        path = self.sysbus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER)
        self.server = dbus.Interface(path, avahi.DBUS_INTERFACE_SERVER)

    @property
    def version(self):
        return str(self.server.GetVersionString())

    @property
    def apiVersion(self):
        return str(self.server.GetAPIVersion())

    @property
    def hostname(self):
        return str(self.server.GetHostName())

    @property
    def domain(self):
        return str(self.server.GetDomainName())

    @property
    def fqdn(self):
        return str(self.server.GetHostNameFqdn())

    def newGroup(self):
        path = self.sysbus.get_object(avahi.DBUS_NAME, self.server.EntryGroupNew())
        return dbus.Interface(path, avahi.DBUS_INTERFACE_ENTRY_GROUP)


class NotifyHandler(socketserver.BaseRequestHandler):
    # FIXME: Find a way to enable SOCK_REUSEADDR

    def handle(self):
        self.data = self.request.recv(8192)
        try:
            q.put_nowait(True)
        except queue.Full:
            print('avahi-publisher: Warning: queue is full')
            pass
        try:
            notify = dns.message.from_wire(self.data)
            print('avahi-publisher: DNS NOTIFY for %s', notify.query[0].name)

            res = dns.message.make_response(notify)
            res.flags |= dns.flags.AA
            self.request.sendall(res)
        except dns.exception.DNSException:
            # For some reason, dnspython fails to parse the NOTIFY
            # message send by knot, so let's ignore it. In this case
            # it does not matter anyway, we don't need to read the
            # notify. We can use the connection attempt as a hint to
            # start AXFR. Knot will write a warning into its logs, but
            # everything will work as expected.
            pass


def rdata2avahi(rdata):
    buf = io.BytesIO()
    rdata.to_wire(buf)
    rv = []
    for c in buf.getvalue():
        rv.append(dbus.Byte(c))
    return rv


def _wait(group):
    print('avahi-publisher: Waiting for Avahi to finish....')
    while True:
        v = group.GetState()
        if v == 2:
            break
        sleep(1.0)
    print('avahi-publisher: Avahi finished.')


def sync(domain, zone, serial):
    print("avahi-publisher: Pushing zone %s [serial %s] to Avahi" % (domain, serial))

    keep = dict()

    for name, ttl, rdata in zone.iterate_rdatas():
        type_ = rdata.rdtype
        if type_ == dns.rdatatype.SOA: continue
        elif type_ == dns.rdatatype.NS: continue

        key = '%s,%s,%d,%s' % (name, domain, rdata.rdtype, rdata.to_text(name))

        d = avahi_groups.get(domain, None)
        if d is None:
            d = dict()
            avahi_groups[domain] = d

        group = d.get(key, None)
        if group is None:
            group = avahi_daemon.newGroup()
            d[key] = group

            if DEBUG is not None:
                print('avahi-publisher:\t+ %s\t%d\t%s\t%s\t%s' % (name, ttl,
                    dns.rdataclass.to_text(rdata.rdclass),
                    dns.rdatatype.to_text(rdata.rdtype),
                    rdata.to_text(name)))

            group.AddRecord(avahi.IF_UNSPEC, avahi.PROTO_INET, 0,
                str(name), rdata.rdclass, rdata.rdtype, ttl if ttl > 0 else DEFAULT_TTL, rdata2avahi(rdata))
            group.Commit()
        keep[key] = group

    d = avahi_groups.get(domain, None)
    if d is None:
        d = dict()
        avahi_groups[domain] = d

    keys = list(d.keys())
    for k in keys:
        if k in keep: continue
        if DEBUG is not None:
            print('avahi-publisher:\t- %s' % k)
        d[k].Free()
        del d[k]



def run():
    global serials, q

    while True:
        for domain in DOMAINS:
            zone = dns.zone.from_xfr(dns.query.xfr(DNS_SERVER, domain, relativize=False), relativize=False)

            SOARecord = zone.get_rdataset(domain, 'SOA')
            if SOARecord == None:
                SOARecord = zone.get_rdataset(domain + '.', 'SOA')
            serial = SOARecord[0].serial
            if serial == serials.get(domain, None):
                continue
            serials[domain] = serial

            sync(domain, zone, serial)

        try:
            v = q.get(timeout=INTERVAL)
            q.task_done()

            # Skip any update notifications accumulated in the queue.
            # We want to fetch the most recent zone from the DNS
            # server anyway.
            while True:
                try:
                    v = q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break

        except queue.Empty:
            pass



def start_notify_listener():
    print("avahi-publisher: Starting DNS NOTIFY listener on tcp:%s:%d" % (LISTEN_ADDRESS, LISTEN_PORT))

    server = socketserver.TCPServer((LISTEN_ADDRESS, LISTEN_PORT), NotifyHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    avahi_daemon = AvahiDaemon()
    print("avahi-publisher: Connected to Avahi Daemon: %s (API %s) [%s]"
          % (avahi_daemon.version, avahi_daemon.apiVersion, avahi_daemon.fqdn))
    print("avahi-publisher: Transferring zones %s from %s" % (repr(DOMAINS), DNS_SERVER))
    start_notify_listener()

    run()
