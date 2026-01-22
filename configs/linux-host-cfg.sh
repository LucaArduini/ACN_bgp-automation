#!/bin/bash
ip link add mgmt type vrf table 1001
ip link set mgmt up
ip link set eth0 master mgmt
ip route add table 1001 default via 172.20.20.1 dev eth0

ip link set $MY_INTF up
ip addr flush dev $MY_INTF
ip addr add $MY_IP dev $MY_INTF

if [ ! -z "$MY_GW" ]; then
    ip route del default 2>/dev/null
    ip route add default via $MY_GW
fi