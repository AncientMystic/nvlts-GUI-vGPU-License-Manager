package main

import (
	"os"
	"os/exec"
)

const (
	TS_DIRECTORY      = "C:/Program Files/NVIDIA Corporation/vGPU Licensing/TrustedStorage"
	TS_ENCRYPTED_FILE = TS_DIRECTORY + "/NGUgNGMgNTMgMzEgMmUgMzA"
	TS_TAG_FILE       = TS_DIRECTORY + "/DataStore.bin"
)

func restartService() {
	if !autoRestart {
		return
	}

	cmd := exec.Command("powershell.exe", "Restart-Service", "NVDisplay.ContainerLocalSystem")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Run()
}
