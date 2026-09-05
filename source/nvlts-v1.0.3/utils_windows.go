package main

import (
	"fmt"
	"net"
	"strings"
	"unsafe"

	"github.com/yusufpapurcu/wmi"
	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/registry"
)

func GetAdaptersInfo(query QueryType) ([]string, error) {
	var results []string

	flags := uint32(windows.GAA_FLAG_SKIP_ANYCAST |
		windows.GAA_FLAG_SKIP_MULTICAST |
		windows.GAA_FLAG_SKIP_DNS_SERVER |
		windows.GAA_FLAG_INCLUDE_PREFIX)
	family := uint32(windows.AF_UNSPEC)

	size := uint32(15000)
	buf := make([]byte, size)
	err := windows.GetAdaptersAddresses(family, flags, 0, (*windows.IpAdapterAddresses)(unsafe.Pointer(&buf[0])), &size)
	if err != nil {
		return nil, fmt.Errorf("GetAdaptersInfo failed, error: %s", err)
	}

	addr := (*windows.IpAdapterAddresses)(unsafe.Pointer(&buf[0]))
	for ; addr != nil; addr = addr.Next {
		if addr.IfType == windows.IF_TYPE_SOFTWARE_LOOPBACK {
			continue
		}

		switch query {
		case MACAddress:
			if addr.PhysicalAddressLength > 0 {
				results = append(results, strings.ToUpper(net.HardwareAddr(addr.PhysicalAddress[:addr.PhysicalAddressLength]).String()))
			}

		case IPAddress:
			unicast := addr.FirstUnicastAddress
			for ; unicast != nil; unicast = unicast.Next {
				sa := unicast.Address
				switch sa.Sockaddr.Addr.Family {
				case windows.AF_INET:
					ip := (*windows.RawSockaddrInet4)(unsafe.Pointer(sa.Sockaddr))
					results = append(results, net.IP(ip.Addr[:]).String())
				case windows.AF_INET6:
					ip := (*windows.RawSockaddrInet6)(unsafe.Pointer(sa.Sockaddr))
					results = append(results, net.IP(ip.Addr[:]).String())
				}
			}
		}
	}

	return results, nil
}

func GetMachineID() (string, error) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Cryptography`, registry.QUERY_VALUE)
	if err != nil {
		return "", fmt.Errorf("failed to open registry: %s", err)
	}
	defer key.Close()

	machineID, _, err := key.GetStringValue("MachineGuid")
	if err != nil {
		return "", fmt.Errorf("failed to read MachineGuid: %s", err)
	}
	return strings.ToUpper(machineID), nil
}

func GetOsPlatform() (string, error) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows NT\CurrentVersion`, registry.QUERY_VALUE)
	if err != nil {
		return "", fmt.Errorf("failed to open registry: %s", err)
	}
	defer key.Close()

	productName, _, err := key.GetStringValue("ProductName")
	if err != nil {
		return "", fmt.Errorf("failed to read ProductName: %s", err)
	}
	return productName, nil
}

func GetOsVersion() (string, error) {
	v := windows.RtlGetVersion()
	return fmt.Sprintf("%d.%d.%d", v.MajorVersion, v.MinorVersion, v.BuildNumber),nil
}

func GetProcessorCount() (socket int, cores uint32, err error) {
	type win32_Processor struct {
		NumberOfCores             uint32
		NumberOfLogicalProcessors uint32
	}

	var processors []win32_Processor
	err = wmi.Query(wmi.CreateQuery(&processors, ""), &processors)
	if err != nil {
		err = fmt.Errorf("failed to read GetProcessorCount: %s", err)
		return
	}

	socket = len(processors)
	for _, processor := range processors {
		cores += processor.NumberOfCores
	}
	return
}
