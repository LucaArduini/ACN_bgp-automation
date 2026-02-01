#!/bin/bash

# Function to get IP addresses and default gateways
get_mgmt_info() {
  mgmt_ipv4_addr=$(ip -4 addr show eth0 | grep inet | awk '{print $2}')
  mgmt_default_ipv4_nh=$(ip route | grep '^default' | awk '{print $3}')
  mgmt_ipv6_addr=$(ip -6 addr show | grep -E '^\s*inet6.*global' | awk '{print $2}')
  mgmt_default_ipv6_nh=$(ip -6 route | grep '^default' | awk '{print $3}')
}

# Function to configure VRF
configure_vrf() {
  sysctl -w net.ipv6.conf.all.keep_addr_on_down=1
  ip link add ${CLAB_MGMT_VRF} type vrf table 1
  ip link set dev ${CLAB_MGMT_VRF} up

  [ -n "${mgmt_default_ipv4_nh}" ] && ip route del default via ${mgmt_default_ipv4_nh}
  [ -n "${mgmt_default_ipv6_nh}" ] && ip -6 route del default via ${mgmt_default_ipv6_nh}

  ip link set dev eth0 master ${CLAB_MGMT_VRF}

  [ -n "${mgmt_default_ipv4_nh}" ] && ip route add default via ${mgmt_default_ipv4_nh} vrf ${CLAB_MGMT_VRF}
  [ -n "${mgmt_default_ipv6_nh}" ] && ip -6 route add default via ${mgmt_default_ipv6_nh} vrf ${CLAB_MGMT_VRF}
}

# Function to configure FRR
configure_frr() {
  vtysh << EOF
configure terminal
interface eth0
ip address ${mgmt_ipv4_addr}
exit
write
EOF

  if [ -n "${mgmt_ipv6_addr}" ]; then
    vtysh << EOF
configure terminal
interface eth0
ipv6 address ${mgmt_ipv6_addr}
exit
write
EOF
  fi
}

echo "starting script"
# Main script execution
get_mgmt_info
echo "mgmt set"
if [ -n "${CLAB_MGMT_VRF}" ]; then
  configure_vrf
fi
echo "vrf configured"

configure_frr
echo "all done"
