#!/bin/bash

#######################################################################################
# This script handles the controlled teardown of the infrastructure.
# Main operations include:
# 1. Destroying the Containerlab topology and removing FRR/Manager containers.
# 2. Cleaning up log files and temporary configurations generated during runtime.
# 3. Removing the Linux bridge interface from the host system.
# It is used to return the server to a clean state before a new deployment.
#######################################################################################

# --- CONFIGURATION ---
TOPOLOGY_SPEC="./topology/network.clab.yml"
BRIDGE_NAME="lan"

# Formatting for console logs
INFO='\033[0;34m[INFO]\033[0m'
SUCCESS='\033[0;32m[OK]\033[0m'
ERROR='\033[0;31m[ERROR]\033[0m'

clear
echo -e "======================================================"
echo -e "   PROJECT BGP AUTOMATION - INFRASTRUCTURE TEARDOWN   "
echo -e "======================================================\n"

# 1. CONTAINERLAB TOPOLOGY REMOVAL
echo -e "$INFO Tearing down Containerlab topology..."
if [ -f "$TOPOLOGY_SPEC" ]; then
    # The --cleanup option deletes node working directories and certificates
    if sudo containerlab destroy -t "$TOPOLOGY_SPEC" --cleanup; then
        echo -e "$SUCCESS Topology removed and temporary files deleted."
    else
        echo -e "$ERROR Error during topology destruction."
    fi
else
    echo -e "$ERROR Topology specification not found at $TOPOLOGY_SPEC."
fi

# 2. LINUX BRIDGE REMOVAL
# Deletes the virtual bridge created for the AS65020 LAN
echo -e "\n$INFO Removing Linux bridge ($BRIDGE_NAME)..."
if ip link show "$BRIDGE_NAME" > /dev/null 2>&1; then
    if sudo ip link delete dev "$BRIDGE_NAME"; then
        echo -e "$SUCCESS Bridge $BRIDGE_NAME removed successfully."
    else
        echo -e "$ERROR Unable to remove bridge $BRIDGE_NAME."
    fi
else
    echo -e "$SUCCESS Bridge $BRIDGE_NAME does not exist or has already been removed."
fi

# 3. IMAGE STATUS (Informational)
# Images are not removed to avoid long download times during the next startup
echo -e "\n$INFO Note: Docker images were not removed to speed up future bootstraps."

echo -e "\n======================================================"
echo -e "   $SUCCESS CLEANUP COMPLETED"
echo -e "======================================================"