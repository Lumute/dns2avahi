# Thanks

mDNS appropriated the .local tld long after Microsoft spent years pushuing it who people as a good practice to build company domains, a lot of companies out there still using .local domains. Renaming a Windows domain although possible is a huge undertake with lots of implications and possible unforseen problems. Now that OSs (like Android 12) started exclusively using mDNS for .local resolution this is a bigger issue and this code is the perfect workaround.

This is a fork of [Jan Janak's dns2avahi](https://github.com/janakj/dns2avahi) (Thanks a lot Jan) with some minor changes to support Windows DNS Servers and a bit of logic to support for separate DNS Server when pulling multiple domains (one each, optional). Also added a couple of files to install it as a service on a Raspberry Pi.


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

If you wish to propagate DNS zone changes to Avahi immediately, configure your DNS server to send DNS NOTIFY to Avahi Publisher. By default, Avahi Publisher listens for DNS NOTIFY on 127.0.0.1:53535. The IP address and port number are configurable with environment variables `LISTEN_ADDRESS` and `LISTEN_PORT`. Upon receiving a DNS NOTIFY, Avahi Publisher synchronizes the DNS zone with Avahi immediately. 

## Avahi Resolver

Avahi Resolver is a Python plugin for [Unbound](https://www.nlnetlabs.nl/projects/unbound/about/). To be able to use the plugin, you may need to recompile Unbound to enable Python 3 support as follows:
```sh
cd unbound
PYTHON_VERSION=3 ./configure --with-libevent --with-pythonmodule
make all
make install
```
The plugin is meant to be used as a fallback resolver that resolves DNS records in multicast DNS if the upstream DNS server cannot be reaached or provides no answer (NXDOMAIN). The following Unbound configuration file snippet shows how to enable the plugin:
```
server:
  module-config: "validator python iterator"
  num-threads: 32
  cache-max-negative-ttl: 60
  cache-max-ttl: 60
```

The behavior of the plugin can be controlled via a number of environment variables that are all documented in [avahi-resolver.py](avahi-resolver.py).

## Docker Containers

The subdirectory [docker](docker) provides Dockerfiles for [Avahi Publisher](docker/Dockerfile.publisher) and [Unbound with Python 3](docker/Dockerfile.unbound) support enabled.


## Installation on a Raspberry Pi
```
- Install avahi-utils (not really necessary but facilitates things with avahi-resolve and avahi-publish, etc.) link
		sudo apt-get install avahi-utils
- Install required phyton modules
		sudo apt-get install python3-pip
		sudo pip3 install pydbus
		sudo pip3 install dnspython
- Install avahi-publisher
		mkdir dns2avahi
		cd dns2avahi
		wget https://raw.githubusercontent.com/Lumute/dns2avahi/main/avahi-publisher.py
		wget https://raw.githubusercontent.com/Lumute/dns2avahi/main/avahi.py
- Configure it to run as a system service
		wget https://raw.githubusercontent.com/Lumute/dns2avahi/main/dns2avahi.sh
		vi dns2avahi.sh           (edit and modify the execution command as needed with your domain/s and dns server/s)
		dnsh dns2avahi.sh         (Test that it runs fine)
		cd /etc/systemd/system
		sudo wget https://raw.githubusercontent.com/Lumute/dns2avahi/main/systemd/dns2avahi.service
		sudo vi dns2avahi.service
		sudo systemctl start dns2avahi
		sudo systemctl enable dns2avahi
```
		

