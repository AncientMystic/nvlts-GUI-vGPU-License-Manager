package client_configuration_token

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"os"
	"path"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

const (
	DLS_URL                   = "fuck-nvidia.localdomain"
	DLS_PORT                  = 443
	JWT_ID                    = "90000000-0000-0000-0000-000000000001"
	INSTANCE_REF              = "10000000-0000-0000-0000-000000000001"
	ALLOTMENT_REF             = "20000000-0000-0000-0000-000000000001"
)

func Generate() (string, error) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return "", err
	}

	publicKeyBytes, err := x509.MarshalPKIXPublicKey(&privateKey.PublicKey)
	if err != nil {
		return "", err
	}

	public_key_pem := string(pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: publicKeyBytes,
	}))
	public_key_pem = strings.TrimSuffix(public_key_pem, "\n")

	curTime := time.Now().Add(-40 * time.Hour).UTC()
	expTime := time.Date(2099, 12, 31, 23, 59, 59, 9, time.UTC)

	payload := &ClientConfigToken{
		ID:                      JWT_ID,
		Issuer:                  "NLS Service Instance",
		Audience:                "NLS Licensed Client",
		IssuedAt:                curTime.Unix(),
		NotBefore:               curTime.Unix(),
		ExpiresAt:               expTime.Unix(),
		ProtocolVersion:         "2.0",
		UpdateMode:              "ABSOLUTE",
		ScopeRefList:            []string{ALLOTMENT_REF},
		FulfillmentClassRefList: []string{},
		ServiceInstanceConfiguration: ServiceInstanceConfiguration{
			ServiceInstanceRef: INSTANCE_REF,
			SvcPortSetList: []SvcPortSet{
				{
					Idx:   0,
					DName: "DLS",
					SvcPortMap: []SvcPort{
						{Service: "auth", Port: DLS_PORT},
						{Service: "lease", Port: DLS_PORT},
					},
				},
			},
			NodeURLList: []NodeURL{
				{Idx: 0, URL: DLS_URL, URLQr: DLS_URL, SvcPortSetIdx: 0},
			},
		},
		ServiceInstancePublicKeyConfiguration: ServiceInstancePublicKeyConfiguration{
			ServiceInstancePublicKeyME: ServiceInstancePublicKeyME{
				Mod: privateKey.PublicKey.N.String(),
				Exp: privateKey.PublicKey.E,
			},
			ServiceInstancePublicKeyPEM: public_key_pem,
			KeyRetentionMode:            "LATEST_ONLY",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, payload)
	return token.SignedString(privateKey)
}

func GenerateAndWrite() error {
	data, err := Generate()
	if err != nil {
		return err
	}

	os.MkdirAll(path.Dir(GENERATE_FILE), 0644)
	return os.WriteFile(GENERATE_FILE, []byte(data), 0644)
}
