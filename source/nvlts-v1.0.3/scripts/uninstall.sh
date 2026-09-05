#!/bin/bash
print_black() {
    echo -e "\033[30m$1\033[0m"
}

print_red() {
    echo -e "\033[31m$1\033[0m"
}

print_green() {
    echo -e "\033[32m$1\033[0m"
}

print_yellow() {
    echo -e "\033[33m$1\033[0m"
}

print_blue() {
    echo -e "\033[34m$1\033[0m"
}

print_magenta() {
    echo -e "\033[35m$1\033[0m"
}

print_cyan() {
    echo -e "\033[36m$1\033[0m"
}

print_grey() {
    echo -e "\033[37m$1\033[0m"
}

print_white() {
    echo "$1"
}

clear
PROGRAM="nvlts"

print_cyan "$PROGRAM uninstallation script"

# Read parameters
{
    while [ $# -gt 0 ]; do
        case $1 in
        *)
            print_red " Unknown parameter: $1"
            exit 2
            ;;
        esac
        shift
    done
}

# Check system
{
    print_yellow " ** Checking system info..."

    # Check systemd
    command -V systemctl >/dev/null
    if [ "$?" -ne 0 ]; then
        print_red "Not found systemd"
        exit 1
    fi
}

# Check installed program
{
    print_yellow " ** Checking installation info..."

    if [ ! -d "/opt/nvlts" ]; then
        print_red "No installed program found!"
        exit 1
    fi
}

# Remove files
{
    print_yellow " ** Removing files..."
    rm -f /etc/nvidia/vGPULicense/nvlts.lic
    rm -f /var/lib/nvidia/vGPULicensing/DataStore.bin
    rm -f /var/lib/nvidia/vGPULicensing/NGUgNGMgNTMgMzEgMmUgMzA
    rm -f /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf
}

# Finish uninstallation
{
    systemctl daemon-reload
    systemctl restart nvidia-gridd
}

print_green "$PROGRAM uninstalled successfully"
