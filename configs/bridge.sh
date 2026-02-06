#!/bin/bash
sudo /usr/sbin/ip link add name lan type bridge
sudo /usr/sbin/ip link set dev lan up