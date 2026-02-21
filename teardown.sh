#!/bin/bash

#######################################################################################
# Questo script si occupa dello smantellamento controllato dell'infrastruttura.
# Le operazioni principali includono:
# 1. Distruzione della topologia Containerlab e rimozione dei container FRR/Manager.
# 2. Pulizia dei file di log e delle configurazioni temporanee generate durante il runtime.
# 3. Rimozione dell'interfaccia bridge Linux dal sistema host.
# Viene utilizzato per riportare il server allo stato pulito prima di un nuovo deploy.
#######################################################################################

# --- CONFIGURAZIONE ---
TOPOLOGY_SPEC="./topology/network.clab.yml"
BRIDGE_NAME="lan"

# Formattazione per i log a console
INFO='\033[0;34m[INFO]\033[0m'
SUCCESS='\033[0;32m[OK]\033[0m'
ERROR='\033[0;31m[ERROR]\033[0m'

clear
echo -e "======================================================"
echo -e "   PROJECT BGP AUTOMATION - INFRASTRUCTURE TEARDOWN   "
echo -e "======================================================\n"

# 1. RIMOZIONE TOPOLOGIA CONTAINERLAB
echo -e "$INFO Smantellamento topologia Containerlab..."
if [ -f "$TOPOLOGY_SPEC" ]; then
    # L'opzione --cleanup elimina le directory di lavoro dei nodi e i certificati
    if sudo containerlab destroy -t "$TOPOLOGY_SPEC" --cleanup; then
        echo -e "$SUCCESS Topologia rimossa e file temporanei eliminati."
    else
        echo -e "$ERROR Errore durante la distruzione della topologia."
    fi
else
    echo -e "$ERROR Specifica della topologia non trovata in $TOPOLOGY_SPEC."
fi

# 2. RIMOZIONE BRIDGE LINUX
# Elimina il bridge virtuale creato per la LAN di AS65020
echo -e "\n$INFO Rimozione del bridge Linux ($BRIDGE_NAME)..."
if ip link show "$BRIDGE_NAME" > /dev/null 2>&1; then
    if sudo ip link delete dev "$BRIDGE_NAME"; then
        echo -e "$SUCCESS Bridge $BRIDGE_NAME rimosso correttamente."
    else
        echo -e "$ERROR Impossibile rimuovere il bridge $BRIDGE_NAME."
    fi
else
    echo -e "$SUCCESS Il bridge $BRIDGE_NAME non esiste o è già stato rimosso."
fi

# 3. STATO IMMAGINI (Informativo)
# Le immagini non vengono rimosse per evitare lunghi tempi di download al prossimo avvio
echo -e "\n$INFO Nota: Le immagini Docker non sono state rimosse per velocizzare i futuri bootstrap."

echo -e "\n======================================================"
echo -e "   $SUCCESS PULIZIA COMPLETATA"
echo -e "======================================================"