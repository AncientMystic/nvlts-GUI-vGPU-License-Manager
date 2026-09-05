//go:build net

/*
* Never call on Linux?
* It will call on Windows after RDP Logon
* Tested on 18.0, 18.1, 18.2
 */

package main

import (
	"encoding/json"
	"fmt"
	"nvlts/client_configuration_token"
	"time"
)

const (
	TS_LEASE_DATE_FORMAT = "2006-01-02T15:04:05.999999Z"
	LEASE_LIST           = "    {\n" +
		"      \"product\":{\n" +
		"        \"name\":\"%s\",\n" +
		"        }\n" +
		"       \"license_type_qualifier\":{\n" +
		"        \"count\":%d\n" +
		"        }\n" +
		"      }"
	LEASE_TS_SCHEMA = "{    %s  \"refresh_count\":%d,\n    \"request\":%s\n   }"
)

func (cfg *TrustedStore) generate() (string, error) {
	err := client_configuration_token.GenerateAndWrite()
	if err != nil {
		return "", err
	}

	origin, err := cfg.generateOrigin(cfg.generateSystemClockSnapshot())
	if err != nil {
		return "", err
	}

	lease, err := cfg.generateLease()
	if err != nil {
		return "", err
	}

	lease_ts, err := cfg.generateLeaseTS(lease, cfg.generateLeaseList())
	if err != nil {
		return "", err
	}

	return cfg.generateTS(origin, lease_ts), nil
}

func (cfg *TrustedStore) generateLease() (string, error) {
	expires := time.Date(2099, 12, 31, 23, 59, 59, 9, time.UTC).Format(TS_LEASE_DATE_FORMAT)
	if !cfg.Expires.IsZero() {
		expires = cfg.Expires.UTC().Format(TS_LEASE_DATE_FORMAT)
	}

	data, err := json.Marshal(map[string]any{
		"created":                   cfg.Created.UTC().Format(TS_LEASE_DATE_FORMAT),
		"expires":                   expires,
		"feature_name":              cfg.FeatureName,
		"lease_intent_id":           nil,
		"license_type":              "CONCURRENT_COUNTED_SINGLE",
		"metadata":                  nil,
		"offline_lease":             true, // Do not return lease if an offline usage is granted
		"product_name":              cfg.ProductName,
		"recommended_lease_renewal": 0.8, // Renewal timer is the [remaining time (exp - cur) * recommended_lease_renewal]
		"ref":                       cfg.Ref,
	})
	if err != nil {
		return "", err
	}

	return string(data[1 : len(data)-1]), nil
}

func (cfg *TrustedStore) generateLeaseList() string {
	return fmt.Sprintf(LEASE_LIST,
		cfg.ProductName,
		1,
	)
}

func (cfg *TrustedStore) generateLeaseTS(lease, lease_list string) (string, error) {
	return fmt.Sprintf(LEASE_TS_SCHEMA,
		lease,
		0,
		lease_list,
	), nil
}
