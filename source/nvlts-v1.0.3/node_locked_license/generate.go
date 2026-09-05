package node_locked_license

import (
	"os"
	"path"
)

func GenerateAndWrite() error {
	os.MkdirAll(path.Dir(GENERATE_FILE), 0644)
	return os.WriteFile(GENERATE_FILE, nil, 0644)
}
