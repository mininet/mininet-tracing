#!/bin/bash

processors=`ls -1 /sys/devices/system/cpu | grep -e "cpu[0-9]\{1,\}" | wc -l`

function warn {
    # Echo the provided command in color text.
    yellow='\e[0;33m' # Yellow
    reset='\e[0m'
    echo="echo -e"
    $echo "${yellow}$1${reset}"
}

function set_cores {
    #Cannot enable/disable cpu0
    for ((i=1; i < $1; i++))
    do
        warn "Enabling cpu ${i}"
        sudo sh -c "echo 1 > /sys/devices/system/cpu/cpu${i}/online"
    done
    for ((i=$i; i < $processors; i++))
    do
        warn "Disabling cpu ${i}"
        sudo sh -c "echo 0 > /sys/devices/system/cpu/cpu${i}/online"
    done
}

function usage {
    warn "Usage: mod-cores.sh [num cores]"
}

if [[ $# -lt 1 ]] 
then
    warn "Enabling all cores"
    set_cores $processors
else
    if [[ $1 -gt $processors || $1 -le 0 ]]; then
        warn "Error: You can only set 1-${processors} cores"
        usage
        exit
    fi
    warn "Enabling ${1} cores"
    set_cores $1
fi
