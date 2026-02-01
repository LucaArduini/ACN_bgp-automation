#!/bin/bash
ip link add mgmt type vrf table 1001
ip link set mgmt up
ip link set eth0 master mgmt
ip route add table 1001 default via 10.255.255.0 dev eth0
#udhcpc -i eth1
ip addr add dev eth1 $MY_IP
ip route add default via $MY_GW