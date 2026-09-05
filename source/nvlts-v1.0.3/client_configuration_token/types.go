package client_configuration_token

import (
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// NVIDIA does not use the json library to process it.
// Must use struct to ensure order
type ClientConfigToken struct {
	ID                                    string                                `json:"jti"`
	Issuer                                string                                `json:"iss"`
	Audience                              string                                `json:"aud"`
	IssuedAt                              int64                                 `json:"iat"`
	NotBefore                             int64                                 `json:"nbf"`
	ExpiresAt                             int64                                 `json:"exp"`
	ProtocolVersion                       string                                `json:"protocol_version"`
	UpdateMode                            string                                `json:"update_mode"`
	ScopeRefList                          []string                              `json:"scope_ref_list"`
	FulfillmentClassRefList               []string                              `json:"fulfillment_class_ref_list"`
	ServiceInstanceConfiguration          ServiceInstanceConfiguration          `json:"service_instance_configuration"`
	ServiceInstancePublicKeyConfiguration ServiceInstancePublicKeyConfiguration `json:"service_instance_public_key_configuration"`
}

type ServiceInstanceConfiguration struct {
	ServiceInstanceRef string       `json:"nls_service_instance_ref"`
	SvcPortSetList     []SvcPortSet `json:"svc_port_set_list"`
	NodeURLList        []NodeURL    `json:"node_url_list"`
}

type SvcPortSet struct {
	Idx        int       `json:"idx"`
	DName      string    `json:"d_name"`
	SvcPortMap []SvcPort `json:"svc_port_map"`
}

type SvcPort struct {
	Service string `json:"service"`
	Port    int    `json:"port"`
}

type NodeURL struct {
	Idx           int    `json:"idx"`
	URL           string `json:"url"`
	URLQr         string `json:"url_qr"`
	SvcPortSetIdx int    `json:"svc_port_set_idx"`
}

type ServiceInstancePublicKeyConfiguration struct {
	ServiceInstancePublicKeyME  ServiceInstancePublicKeyME `json:"service_instance_public_key_me"`
	ServiceInstancePublicKeyPEM string                     `json:"service_instance_public_key_pem"`
	KeyRetentionMode            string                     `json:"key_retention_mode"`
}

type ServiceInstancePublicKeyME struct {
	Mod string `json:"mod"`
	Exp int    `json:"exp"`
}

// GetExpirationTime implements the Claims interface.
func (c ClientConfigToken) GetExpirationTime() (*jwt.NumericDate, error) {
	return jwt.NewNumericDate(time.Unix(c.ExpiresAt, 0)), nil
}

// GetNotBefore implements the Claims interface.
func (c ClientConfigToken) GetNotBefore() (*jwt.NumericDate, error) {
	return jwt.NewNumericDate(time.Unix(c.NotBefore, 0)), nil
}

// GetIssuedAt implements the Claims interface.
func (c ClientConfigToken) GetIssuedAt() (*jwt.NumericDate, error) {
	return jwt.NewNumericDate(time.Unix(c.IssuedAt, 0)), nil
}

// GetAudience implements the Claims interface.
func (c ClientConfigToken) GetAudience() (jwt.ClaimStrings, error) {
	return []string{c.Audience}, nil
}

// GetIssuer implements the Claims interface.
func (c ClientConfigToken) GetIssuer() (string, error) {
	return c.Issuer, nil
}

// GetSubject implements the Claims interface.
func (c ClientConfigToken) GetSubject() (string, error) {
	return "", nil
}
