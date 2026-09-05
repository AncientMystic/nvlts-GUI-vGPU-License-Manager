package main

import (
	"strings"
)

type QueryType int

const (
	MACAddress QueryType = iota
	IPAddress
)

func encode(strs []string) string {
	list := make([]string, 0, len(strs))
	for _, str := range strs {
		list = append(list, `"`+str+`"`)
	}

	return strings.Join(list, ",")
}
