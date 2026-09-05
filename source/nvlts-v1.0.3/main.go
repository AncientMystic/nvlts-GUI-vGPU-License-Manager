package main

import (
	"crypto/aes"
	"crypto/cipher"
	"encoding/json"
	"flag"
	"nvlts/client_configuration_token"
	"os"
	"time"

	"gitlab.com/CoiaPrant/clog"
)

const (
	NVIDIA_LOCAL_TRUSTED_STORAGE_KEY = "477269644c6963656e73696e67322e30"
	NVIDIA_LOCAL_TRUSTED_STORAGE_IV  = "477269644956"

	ORIGIN_REF = "90000000-0000-0000-0000-000000000002"
	TS_REF     = "90000000-0000-0000-0000-000000000003"
)

var (
	autoRestart = false
	gcm         cipher.AEAD
	iv          []byte
)

func initCipher() {
	key := []byte(NVIDIA_LOCAL_TRUSTED_STORAGE_KEY)
	iv = []byte(NVIDIA_LOCAL_TRUSTED_STORAGE_IV)

	block, err := aes.NewCipher(key)
	if err != nil {
		clog.Fatalf("Failed to init AES cipher: %s", err)
		return
	}

	gcm, err = cipher.NewGCM(block)
	if err != nil {
		clog.Fatalf("Failed to init AES-GCM cipher: %s", err)
		return
	}

	clog.Successf("NVIDIA Local Trusted Store AES-GCM cipher initialized successfully")
}

func main() {
	var flagEncrypt, flagDecrypt, flagGenerate bool
	var config, file string

	flag.BoolVar(&flagEncrypt, "e", false, "Encrypt file to NVIDIA Local Trusted Store")
	flag.BoolVar(&flagDecrypt, "d", false, "Decrypt NVIDIA Local Trusted Store to file")
	flag.StringVar(&file, "f", "trusted_store.json", "File to encrypt / save decrypted")
	flag.BoolVar(&flagGenerate, "g", false, "Generate license to NVIDIA Local Trusted Store")
	flag.StringVar(&config, "c", "config.json", "Generate config")
	flag.BoolVar(&autoRestart, "r", false, "Auto restart NVDisplay.ContainerLocalSystem service")
	debug := flag.Bool("debug", false, "Show debug logs")
	help := flag.Bool("h", false, "Show help")
	flag.Parse()

	if *help {
		flag.PrintDefaults()
		return
	}

	if *debug {
		clog.SetLevel(clog.LevelDebug)
	}

	check := checkArgument(flagEncrypt, flagDecrypt, flagGenerate)
	if check < 1 {
		clog.Fatal("Please specify an operation!")
		return
	}

	if check > 1 {
		clog.Fatal("Multiple operations cannot be specified at the same time!")
		return
	}

	initCipher()

	switch {
	case flagEncrypt:
		if file == "" {
			clog.Fatal("Please specify a file!")
			return
		}

		encrypt(file)
	case flagDecrypt:
		if file == "" {
			clog.Fatal("Please specify a file!")
			return
		}

		decrypt(file)
	case flagGenerate:
		if config == "" {
			clog.Fatal("Please specify a config!")
			return
		}

		generate(config)
	}
}

func checkArgument(args ...bool) int {
	sum := 0

	for _, arg := range args {
		if arg {
			sum++
		}
	}

	return sum
}

func encrypt(fromFile string) {
	data, err := os.ReadFile(fromFile)
	if err != nil {
		clog.Errorf("Failed to read '%s', error: %s", fromFile, err)
		return
	}

	encrypted := gcm.Seal(nil, iv, data, nil)

	tagOffset := len(encrypted) - 16
	ciphertext := encrypted[:tagOffset]
	tag := encrypted[tagOffset:]

	os.MkdirAll(TS_DIRECTORY, 0644)

	err = os.WriteFile(TS_ENCRYPTED_FILE, ciphertext, 0644)
	if err != nil {
		clog.Errorf("Failed to save to '%s', error: %s", TS_ENCRYPTED_FILE, err)
		return
	}

	err = os.WriteFile(TS_TAG_FILE, tag, 0644)
	if err != nil {
		clog.Errorf("Failed to save to '%s', error: %s", TS_TAG_FILE, err)
		return
	}

	clog.Successf("File encrypted and write successfully")
	restartService()
}

func decrypt(toFile string) {
	encrypted, err := os.ReadFile(TS_ENCRYPTED_FILE)
	if err != nil {
		clog.Errorf("Failed to read '%s', error: %s", TS_ENCRYPTED_FILE, err)
		return
	}

	tag, err := os.ReadFile(TS_TAG_FILE)
	if err != nil {
		clog.Errorf("Failed to open '%s', error: %s", TS_TAG_FILE, err)
		return
	}

	decrypted, err := gcm.Open(nil, iv, append(encrypted, tag...), nil)
	if err != nil {
		clog.Errorf("Failed to decrypt, error: %s", err)
		return
	}

	err = os.WriteFile(toFile, decrypted, 0644)
	if err != nil {
		clog.Errorf("Failed to save, error: %s", err)
		return
	}

	clog.Successf("File decrypted and write successfully")
}

func generate(config string) {
	cfgData, err := os.ReadFile(config)
	if err != nil {
		clog.Errorf("Failed to open '%s', error: %s", config, err)
		return
	}

	var cfg Config
	err = json.Unmarshal(cfgData, &cfg)
	if err != nil {
		clog.Errorf("Failed to read config, error: %s", err)
		return
	}

	systemTime := time.Now()
	trustedStore := &TrustedStore{
		ClockSnapshot: systemTime.Add(-36 * time.Hour),
		JWT_ID:        client_configuration_token.JWT_ID,
		OriginRef:     ORIGIN_REF,
		Config:        cfg,
		Created:       systemTime.Add(-38 * time.Hour),
		Ref:           TS_REF,
	}
	payload, err := trustedStore.generate()
	if err != nil {
		clog.Errorf("Failed to generate, error: %s", err)
		return
	}

	encrypted := gcm.Seal(nil, iv, []byte(payload), nil)

	tagOffset := len(encrypted) - 16
	ciphertext := encrypted[:tagOffset]
	tag := encrypted[tagOffset:]

	err = os.WriteFile(TS_ENCRYPTED_FILE, ciphertext, 0644)
	if err != nil {
		clog.Errorf("Failed to save to '%s', error: %s", TS_ENCRYPTED_FILE, err)
		return
	}

	err = os.WriteFile(TS_TAG_FILE, tag, 0644)
	if err != nil {
		clog.Errorf("Failed to save to '%s', error: %s", TS_TAG_FILE, err)
		return
	}
	clog.Successf("File generated and write successfully")

	restartService()
}
