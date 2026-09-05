package main

import (
	"fmt"
	"os"
	"time"

	"github.com/klauspost/cpuid/v2"
)

// The content is not strictly JSON.
// NVIDIA does not use the json library to process it.
// It uses snprintf to concatenate strings.
const (
	TS_SCHEMA_SYSTEM_CLOCK_SNAPSHOT             = "    \"system_clock_snapshot\":\"%s\",\n    \"jti\":\"%s\",\n"
	TS_SCHEMA_SYSTEM_CLOCK_SNAPSHOT_DATE_FORMAT = "2006-01-02T15:04:05"

	TS_SCHEMA_ORGIN = "%s    \"origin\": {\n" +
		"    \"origin_ref\":\"%s\",\n" +
		"    \"environment\":{\n" +
		"      \"fingerprint\":{\n" +
		"        \"mac_address_list\":[%s],\n" +
		"        }\n" +
		"      \"ip_address_list\":[%s],\n" +
		"      \"hostname\":\"%s\",\n" +
		"      \"guest_driver_version\":\"%s\",\n" +
		"      \"os_platform\":\"%s\",\n" +
		"      \"os_version\":\"%s\",\n" +
		"    \"host_driver_version\":\"%s\",\n" +
		"      \"gpu_id_list\":[%s],\n" +
		"      \"client_platform_id\":\"%s\",\n" +
		"    \"hv_platform\":\"%s\",\n" +
		"      \"cpu_sockets\":%d,\n" +
		"      \"physical_cores\":%d}\n" +
		"    \"registered\":%s,\n" +
		"    \"failed_registration_attempts\":%s}"

	TS_SCHEMA = "{\n" +
		"%s,\n" +
		"  \"lease_management\": {\n" +
		"    \"lease_list\": {[%s],\n" +
		"    \"lease_state\":\"%s\",\n" +
		"    \"lease_owner_session\":\"%d\"}  }\n" +
		"}"
	TS_LEASE_STATE_ACTIVE = "ACTIVE"
)

type Config struct {
	GuestDriverVersion string
	HostDriverVersion  string
	ProductName        string
	FeatureName        string
	FeatureVersion     string
	GPU                []string
}

type TrustedStore struct {
	ClockSnapshot time.Time
	JWT_ID        string
	OriginRef     string
	Config

	Created time.Time
	Expires time.Time
	Ref     string
}

func (cfg *TrustedStore) generateSystemClockSnapshot() string {
	return fmt.Sprintf(TS_SCHEMA_SYSTEM_CLOCK_SNAPSHOT,
		cfg.ClockSnapshot.UTC().Format(TS_SCHEMA_SYSTEM_CLOCK_SNAPSHOT_DATE_FORMAT),
		cfg.JWT_ID)
}

func (cfg *TrustedStore) generateOrigin(systemClockSnapshot string) (string, error) {
	macAddressList, err := GetAdaptersInfo(MACAddress)
	if err != nil {
		return "", err
	}

	ipAddressList, err := GetAdaptersInfo(IPAddress)
	if err != nil {
		return "", err
	}

	hostname, err := os.Hostname()
	if err != nil {
		return "", err
	}

	machine_id, err := GetMachineID()
	if err != nil {
		return "", err
	}

	hypervisor := "Unknown"
	switch cpuid.CPU.HypervisorVendorID {
	case cpuid.KVM:
		hypervisor = "LINUX_KVM"
	case cpuid.VMware:
		hypervisor = "VMWARE_ESXI"
	case cpuid.MSVM:
		hypervisor = "WINDOWS_SERVER_HYPER_V"
	case cpuid.XenHVM:
		hypervisor = "CITRIX_XEN_SERVER"
	}

	os_platform, err := GetOsPlatform()
	if err != nil {
		return "", err
	}

	os_version, err := GetOsVersion()
	if err != nil {
		return "", err
	}

	sockets, cores, err := GetProcessorCount()
	if err != nil {
		return "", err
	}

	return fmt.Sprintf(TS_SCHEMA_ORGIN,
		systemClockSnapshot,
		cfg.OriginRef,
		encode(macAddressList),
		encode(ipAddressList),
		hostname,
		cfg.GuestDriverVersion,
		os_platform,
		os_version,
		cfg.HostDriverVersion,
		encode(cfg.GPU),
		machine_id,
		hypervisor,
		sockets,
		cores,
		"true",
		"0",
	), nil
}

func (cfg *TrustedStore) generateTS(origin, lease_ts string) string {
	return fmt.Sprintf(TS_SCHEMA,
		origin,
		lease_ts,
		TS_LEASE_STATE_ACTIVE,
		0,
	)
}
