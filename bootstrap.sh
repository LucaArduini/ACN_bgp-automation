#!/bin/bash

# --- CONFIGURAZIONE AMBIENTE ---
WAN_INTERFACE="enp0s8"
TEST_TARGET="8.8.8.8"
BRIDGE_CONFIG="./configs/bridge.sh"
TOPOLOGY_SPEC="./topology/network.clab.yml"

# Formattazione per i log
INFO='\033[0;34m[INFO]\033[0m'
SUCCESS='\033[0;32m[OK]\033[0m'
ERROR='\033[0;31m[ERROR]\033[0m'

clear
echo -e "======================================================"
echo -e "   PROJECT BGP AUTOMATION - INFRASTRUCTURE SETUP      "
echo -e "======================================================\n"

# 1. VERIFICA E RIPRISTINO CONNETTIVITÀ WAN
echo -e "$INFO Verifica connettività Internet..."
if ping -c 1 -W 2 $TEST_TARGET > /dev/null 2>&1; then
    echo -e "$SUCCESS Connessione attiva."
else
    echo -e "$ERROR Connessione assente."
    echo -e "$INFO Tentativo di acquisizione indirizzo IP su $WAN_INTERFACE via DHCP..."
    sudo dhcpcd $WAN_INTERFACE
    
    # Attesa per stabilizzazione link
    sleep 5
    
    if ping -c 1 -W 2 $TEST_TARGET > /dev/null 2>&1; then
        echo -e "$SUCCESS Connettività ripristinata."
    else
        echo -e "$ERROR Impossibile connettersi a Internet."
        echo -e "(Il deploy proseguirà utilizzando le immagini in cache locale)"
    fi
fi

# 2. PROVISIONING DEL BRIDGE LINUX
echo -e "\n$INFO Inizializzazione interfacce bridge..."
if [ -f "$BRIDGE_CONFIG" ]; then
    chmod +x "$BRIDGE_CONFIG"
    if sudo "$BRIDGE_CONFIG"; then
        echo -e "$SUCCESS Linux Bridge configurato correttamente."
    else
        echo -e "$ERROR Fallimento durante l'esecuzione di bridge.sh."
        exit 1
    fi
else
    echo -e "$ERROR Script bridge non trovato in $BRIDGE_CONFIG."
    exit 1
fi

# 3. COSTRUZIONE IMMAGINE MANAGER
echo -e "\n[INFO] Costruzione immagine Docker per il Manager..."
if sudo docker build -t acn-manager:latest -f Dockerfile.manager .; then
     echo -e "[OK] Immagine acn-manager costruita con successo."
else
     echo -e "[ERROR] Fallimento durante la costruzione dell'immagine Docker."
     exit 1
fi

# 4. DEPLOY DELLA TOPOLOGIA DI RETE (CONTAINERLAB)
echo -e "\n[INFO] Avvio del deployment della topologia di rete..."
if [ -f "$TOPOLOGY_SPEC" ]; then
    # Usiamo l'immagine locale appena costruita e i file già presenti
    if sudo containerlab deploy -t "$TOPOLOGY_SPEC" --reconfigure; then
         echo -e "\n======================================================"
         echo -e "   $SUCCESS INFRASTRUTTURA DISTRIBUITA CON SUCCESSO"
         echo -e "======================================================"
    else
         echo -e "\n$ERROR Errore critico durante il deployment con Containerlab."
         exit 1
    fi
else
    echo -e "$ERROR Specifica della topologia non trovata in $TOPOLOGY_SPEC."
    exit 1
fi