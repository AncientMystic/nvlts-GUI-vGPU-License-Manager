package main

import (
	"errors"
	"fmt"
	"net"
	"net/netip"
	"os"
	"strconv"
	"strings"
)

func GetAdaptersInfo(query QueryType) ([]string, error) {
	var results []string

	switch query {
	case MACAddress:
		ifaces, err := net.Interfaces()
		if err != nil {
			return nil, fmt.Errorf("GetAdaptersInfo failed, error: %s", err)
		}

		for _, iface := range ifaces {
			if iface.Name == "lo" {
				continue
			}

			results = append(results, iface.HardwareAddr.String())
		}

	case IPAddress:
		ifaces, err := net.Interfaces()
		if err != nil {
			return nil, fmt.Errorf("GetAdaptersInfo failed, error: %s", err)
		}

		var v4, v6 []string
		for _, iface := range ifaces {
			if iface.Name == "lo" {
				continue
			}

			addrs, err := iface.Addrs()
			if err != nil {
				return nil, fmt.Errorf("GetAdaptersInfo failed, error: %s", err)
			}

			for _, addr := range addrs {
				ipNet, ok := addr.(*net.IPNet)
				if !ok {
					return nil, fmt.Errorf("GetAdaptersInfo failed, error: addr excepted *net.IPNet, but got %T", addr)
				}

				ip, ok := netip.AddrFromSlice(ipNet.IP)
				if !ok {
					continue
				}

				switch {
				case len(ipNet.Mask) == net.IPv4len:
					v4 = append(v4, ipNet.IP.String())
				case ip.Is4In6():
					v6 = append(v6, ip.String())
				case ip.Is6():
					if ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() {
						ip = ip.WithZone(iface.Name)
					}

					v6 = append(v6, ip.String())
				}
			}
		}

		results = make([]string, 0, len(v4)+len(v6))
		results = append(results, v4...)
		results = append(results, v6...)
	}

	return results, nil
}

func GetMachineID() (string, error) {
	data, err := os.ReadFile("/sys/class/dmi/id/product_uuid")
	if err != nil {
		return "", fmt.Errorf("failed to read /sys/class/dmi/id/product_uuid: %s", err)
	}

	return strings.TrimSpace(string(data)), nil
}

func GetOsPlatform() (string, error) {
	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return "", fmt.Errorf("failed to read /etc/os-release: %s", err)
	}

	var osName, osVer string

	items := strings.Split(string(data), "\n")
	for _, item := range items {
		key, value, _ := strings.Cut(item, "=")
		value = strings.TrimPrefix(value, "\"")
		value = strings.TrimSuffix(value, "\"")
		switch key {
		case "PRETTY_NAME":
			osName = value
		case "VERSION_ID":
			osVer = value
		}
	}

	return osName + " " + osVer, nil
}

func GetOsVersion() (string, error) {
	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return "", fmt.Errorf("failed to read /etc/os-release: %s", err)
	}

	items := strings.Split(string(data), "\n")
	for _, item := range items {
		key, value, _ := strings.Cut(item, "=")
		value = strings.TrimPrefix(value, "\"")
		value = strings.TrimSuffix(value, "\"")
		if key == "VERSION" {
			return value, nil
		}
	}

	return "", errors.New("VERSION not found in /etc/os-release")
}

func GetProcessorCount() (socket int, cores uint32, err error) {
	data, err := os.ReadFile("/proc/cpuinfo")
	if err != nil {
		err = fmt.Errorf("failed to read /etc/os-release: %s", err)
		return
	}

	sockets := make(map[string]struct{})

	items := strings.Split(string(data), "\n")
	for _, item := range items {
		key, value, _ := strings.Cut(item, ": ")
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)

		switch key {
		case "cpu cores":
			if i, err := strconv.ParseInt(value, 10, 32); err == nil {
				cores += uint32(i)
			}
		case "physical id":
			sockets[value] = struct{}{}
		}
	}

	socket = len(sockets)
	return
}
