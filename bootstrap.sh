#!/bin/bash

#######################################################################################
# This script handles initializing the entire infrastructure on the remote server.
# The process follows four critical phases:
# 1. Restoring internet connectivity (if necessary) to download images.
# 2. Configuring the system-level Linux bridge to simulate the AS65020 LAN.
# 3. Building the custom Docker image for the Manager node (including required scientific libraries).
# 4. Deploying the network topology via Containerlab using the generated YAML file.
#######################################################################################

# --- ENVIRONMENT CONFIGURATION ---
WAN_INTERFACE="enp0s8"
TEST_TARGET="8.8.8.8"
BRIDGE_CONFIG="./configs/bridge.sh"
TOPOLOGY_SPEC="./topology/network.clab.yml"

# Formatting for console logs
INFO='\033[0;34m[INFO]\033[0m'
SUCCESS='\033[0;32m[OK]\033[0m'
ERROR='\033[0;31m[ERROR]\033[0m'

clear
echo -e "======================================================"
echo -e "   PROJECT BGP AUTOMATION - INFRASTRUCTURE SETUP      "
echo -e "======================================================\n"

# 1. WAN CONNECTIVITY VERIFICATION AND RESTORATION
# Ensures the server can reach the internet to pull Docker images
echo -e "$INFO Checking Internet connectivity..."
if ping -c 1 -W 2 $TEST_TARGET > /dev/null 2>&1; then
    echo -e "$SUCCESS Connection active."
else
    echo -e "$ERROR Connection missing."
    echo -e "$INFO Attempting to acquire IP address on $WAN_INTERFACE via DHCP..."
    sudo dhcpcd $WAN_INTERFACE
    
    # Technical wait for link stabilization after DHCP
    sleep 5
    
    if ping -c 1 -W 2 $TEST_TARGET > /dev/null 2>&1; then
        echo -e "$SUCCESS Connectivity restored."
    else
        echo -e "$ERROR Unable to connect to the Internet."
        echo -e "(Deployment will proceed using locally cached images)"
    fi
fi

# 2. LINUX BRIDGE PROVISIONING
# Creates the bridge interface required to connect PE, GW, and Manager in AS65020
echo -e "\n$INFO Initializing bridge interfaces..."
if [ -f "$BRIDGE_CONFIG" ]; then
    chmod +x "$BRIDGE_CONFIG"
    if sudo "$BRIDGE_CONFIG"; then
        echo -e "$SUCCESS Linux Bridge configured correctly."
    else
        echo -e "$ERROR Failure during bridge.sh execution."
        exit 1
    fi
else
    echo -e "$ERROR Bridge script not found at $BRIDGE_CONFIG."
    exit 1
fi

# 3. MANAGER IMAGE BUILDING
# Creates the "intelligent" container equipped with Python, Numpy, and Scipy for BGP optimization
echo -e "\n$INFO Building Docker image for the Manager..."
if sudo docker build -t acn-manager:latest -f Dockerfile.manager .; then
     echo -e "$SUCCESS acn-manager image built successfully."
else
     echo -e "$ERROR Failure during Docker image build."
     exit 1
fi

# 4. NETWORK TOPOLOGY DEPLOYMENT (CONTAINERLAB)
# Starts all FRR nodes and links defined in the topology
echo -e "\n$INFO Starting network topology deployment..."
if [ -f "$TOPOLOGY_SPEC" ]; then
    # --reconfigure forces Containerlab to regenerate files if already present
    if sudo containerlab deploy -t "$TOPOLOGY_SPEC" --reconfigure; then
         echo -e "\n======================================================"
         echo -e "   $SUCCESS INFRASTRUCTURE DEPLOYED SUCCESSFULLY"
         echo -e "======================================================"
    else
         echo -e "\n$ERROR Critical error during Containerlab deployment."
         exit 1
    fi
else
    echo -e "$ERROR Topology specification not found at $TOPOLOGY_SPEC."
    exit 1
fi