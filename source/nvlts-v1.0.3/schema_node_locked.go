//go:build !net

package main

import (
	"fmt"
	"nvlts/node_locked_license"
)

const (
	TS_LEASE             = "{\"name\": \"%s\", \"lease\": {\"ref\": \"%s\", \"expires\": \"%s\", \"activated\": \"%s\"}, \"feature\": {\"feature_name\": \"%s\", \"feature_version\": \"%s\", \"license_type\": \"%s\", \"detail\": {\"count\": \"%d\"}}}\n  "
	TS_LEASE_DATE_FORMAT = "2006-01-02T15:04:05.999999"
	EXPIRES_PERMANENT    = "3000-12-31T23:59:59.069621"
)

func (cfg *TrustedStore) generate() (string, error) {
	err := node_locked_license.GenerateAndWrite()
	if err != nil {
		return "", err
	}

	origin, err := cfg.generateOrigin(cfg.generateSystemClockSnapshot())
	if err != nil {
		return "", err
	}

	return cfg.generateTS(origin, cfg.generateLeaseTS()), nil
}

func (cfg *TrustedStore) generateLeaseTS() string {
	expires := EXPIRES_PERMANENT
	if !cfg.Expires.IsZero() {
		expires = cfg.Expires.UTC().Format(TS_LEASE_DATE_FORMAT)
	}

	return fmt.Sprintf(TS_LEASE,
		cfg.ProductName,
		cfg.Ref, expires, cfg.Created.UTC().Format(TS_LEASE_DATE_FORMAT),
		cfg.FeatureName, cfg.FeatureVersion, "License_type_1",
		1,
	)
}
