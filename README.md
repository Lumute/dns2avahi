# DNS to Avahi Gateway

This project provides tools to publish and resolve ordinary DNS zones in multicast DNS via [Avahi](https://www.avahi.org). The [`avahi-publisher`](avahi-publisher.py) program downloads an entire DNS zone from the DNS server and publishes all its resource records to multicast DNS via the local Avahi daemon instance. The [`avahi-resolver`](avahi-resolver.py) program implements an extension module for the [Unbound](https://www.nlnetlabs.nl/projects/unbound/about/) DNS resolver that can be used to lookup ordinary DNS queries in multicast DNS via Avahi.

The tools were originally designed to implement peer-to-peer DNS service in an OLSR-based wireless mesh network. The following diagram illustrates the architecture.
![Architecture diagram](https://github.com/janakj/dns2avahi/blob/main/dns2avahi.png?raw=true)
Each node runs a local DNS server serving a DNS zone shared by all nodes in the network. The DNS server has only a subset of the zone's records. An Avahi publisher process makes those records available to the network via Avahi Daemon. Multicast DNS packets from Avahi Daemon are propagated across the OLSR network by [`olsrd`](http://www.olsr.org)'s [multicast forwarding plugin](http://olsr.org/git/?p=olsrd.git;a=blob_plain;f=lib/bmf/README_BMF) (bmf).

DNS queries from clients arrive at Unbound recursive resolver which first attempts to resolve the query in the local DNS server. If no records are found, Unbound forwards the query to Avahi Resolver (Unbound Python extension module) which queries Avahi Daemon for records gathered from other (remote) nodes.

## Avahi Publisher

Avahi Publisher is a Python 3 program that downloads DNS records from the configured server and publishes them to Avahi Daemon. The programm communicates with the DNS server via the standard DNS protocol and with Avahi Daemon via its D-Bus API. Upon startup, the program downloads the entire DNS zone via DNS AXFR, submits its records to Avahi and goes to sleep. Upon receiving a DNS NOTIFY from the DNS server or when a timeout has been reached, the program re-downloads the zone and updates the records in Avahi to make sure they remain synchronized.

Avahi Publisher requires `dbus-python` and `dnspython` libraries. Make sure you have the two libraries installed and start the program as follows:
```sh
DOMAINS="foo.org bar.org" DNS_SERVER=127.0.0.1 python3 avahi-publisher.py
```
The environment variable `DOMAINS` contains a space-delimited list of DNS zones you wish to synchronize. The variable `DNS_SERVER` should contain the IP address of the authoritative DNS server for the zones. Note that the DNS server must be configured to allow DNS AXFR requests from the Avahi Publisher's IP address. By default, Avahi Publisher re-downloads the zones every 60 seconds. The interval can be changed with the environment variable 'INTERVAL'.

## Avahi Resolver
