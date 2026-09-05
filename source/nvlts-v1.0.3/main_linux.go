package main

import (
	"os"
	"os/exec"
)

const (
	TS_DIRECTORY      = "/var/lib/nvidia/vGPULicensing"
	TS_ENCRYPTED_FILE = TS_DIRECTORY + "/NGUgNGMgNTMgMzEgMmUgMzA"
	TS_TAG_FILE       = TS_DIRECTORY + "/DataStore.bin"
)

func restartService() {
	if !autoRestart {
		return
	}

	cmd := exec.Command("systemctl", "restart", "nvidia-gridd")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Run()
}
