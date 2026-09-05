# Guide: Use systemd overlay

1. Create overlay dir

```shell
mkdir -p /etc/systemd/system/nvidia-gridd.service.d
```

2. Copy systemd conf to overlay dir

```shell
cp vApps.conf /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf # vApps
cp vCS.conf /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf # vCS
cp vGaming.conf /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf # vGaming
cp vPC.conf /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf # vPC
cp vWS.conf /etc/systemd/system/nvidia-gridd.service.d/nvlts.conf # vWS
```
