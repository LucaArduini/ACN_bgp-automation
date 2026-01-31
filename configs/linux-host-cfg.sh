#!/bin/bash

ip link show mgmt > /dev/null 2>&1 || ip link add mgmt type vrf table 1001
ip link set mgmt up

ip link set eth0 master mgmt
ip link set eth0 up

ip route add table 1001 172.20.20.0/24 dev eth0 scope link
ip route add table 1001 default via 172.20.20.1 dev eth0

ip link set "$MY_INTF" up
ip addr flush dev "$MY_INTF"
ip addr add "$MY_IP" dev "$MY_INTF"

ip route del default 2>/dev/null

if [ ! -z "$MY_GW" ]; then
    ip route add default via "$MY_GW" dev "$MY_INTF"
fi

sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.$MY_INTF.rp_filter=0
sysctl -w net.ipv4.conf.eth0.rp_filter=0