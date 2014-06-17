#!/bin/bash

echo Creating OpenMotics directory

mkdir -p /opt/openmotics/bin
mkdir -p /opt/openmotics/etc
mkdir -p /opt/openmotics/download

echo Copy OpenMotics software

cp -R python /opt/openmotics/
cp -R Updater /opt/openmotics/
cp -R static /opt/openmotics/

## Copy the bootloader
cp binaries/AN1310cl /opt/openmotics/bin/
cp Bootloader/devices.db /opt/openmotics/bin/
cp binaries/updateController.sh /opt/openmotics/bin

## TODO Place a copy of the hex file on the gateway
touch /opt/openmotics/firmware.hex

## Configure beaglebone ports at boot
cat << EOF > /opt/openmotics/bin/configure_ports.sh
#!/bin/bash
# UART 1
echo 20 > /sys/kernel/debug/omap_mux/uart1_rxd
echo 0 > /sys/kernel/debug/omap_mux/uart1_txd
# UART 2
echo 21 > /sys/kernel/debug/omap_mux/spi0_sclk
echo 1 > /sys/kernel/debug/omap_mux/spi0_d0
# UART 4
echo 26 > /sys/kernel/debug/omap_mux/gpmc_wait0
echo 6 > /sys/kernel/debug/omap_mux/gpmc_wpn
echo 6 > /sys/kernel/debug/omap_mux/lcd_data13
# UART 5
echo 24 > /sys/kernel/debug/omap_mux/lcd_data9
echo 4 > /sys/kernel/debug/omap_mux/lcd_data8
# OpenMotics home LED
echo 7 > /sys/kernel/debug/omap_mux/lcd_data5
echo 75 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio75/direction
echo 1 > /sys/class/gpio/gpio75/value
# Ethernet LEDs
for i in 48 49 60 117;
do
    echo \$i > /sys/class/gpio/export
    echo out > /sys/class/gpio/gpio\${i}/direction
    echo 0 > /sys/class/gpio/gpio\${i}/value
done
# Input button
echo 38 > /sys/class/gpio/export
echo in > /sys/class/gpio/gpio38/direction
echo 26 > /sys/class/gpio/export
echo in > /sys/class/gpio/gpio26/direction
# Master reset output
echo 44 > /sys/class/gpio/export
EOF
chmod +x /opt/openmotics/bin/configure_ports.sh

mount -o remount,rw /

cat << EOF > /etc/supervisor/conf.d/configure_ports.conf 
[program:configure_ports]
command=/opt/openmotics/bin/configure_ports.sh
autostart=true
autorestart=false
directory=/opt/openmotics/bin/
startsecs=0
exitcodes=0
priority=1
EOF

## Install VPN service
cat << EOF > /etc/supervisor/conf.d/vpn_service.conf 
[program:vpn_service]
command=python vpn_service.py
autostart=true
autorestart=true
directory=/opt/openmotics/python
startsecs=10
EOF

## Install OpenVPN service
cat << EOF > /lib/systemd/system/openvpn.service
[Unit]
Description=OpenVPN connection to the OpenMotics cloud

[Service]
ExecStart=/usr/local/sbin/openvpn --config /etc/openvpn/vpn.conf
Restart=always
WorkingDirectory=/etc/openvpn

[Install]
WantedBy=multi-user.target
EOF

ln -s /lib/systemd/system/openvpn.service /lib/systemd/system/multi-user.target.wants/openvpn.service

## Install Openmotics service
cat << EOF > /etc/supervisor/conf.d/openmotics.conf 
[program:openmotics]
command=python openmotics_service.py
autostart=true
autorestart=true
directory=/opt/openmotics/python
startsecs=10
EOF

## Install LED service
cat << EOF > /etc/supervisor/conf.d/led_service.conf 
[program:led_service]
command=python led_service.py
autostart=true
autorestart=true
directory=/opt/openmotics/python
startsecs=10
priority=1
EOF

## Install watchdog
cat << EOF > /etc/supervisor/conf.d/watchdog.conf 
[program:watchdog]
command=python /opt/openmotics/python/watchdog.py
autostart=true
autorestart=false
EOF

## Install Status service to control the LEDs
cat << EOF > /etc/dbus-1/system.d/com.openmotics.status.conf
<!DOCTYPE busconfig PUBLIC
          "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
          "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>

  <policy user="root">
    <allow own="com.openmotics.status"/>
  </policy>

  <policy context="default">
    <allow send_destination="com.openmotics.status"/>
    <allow receive_sender="com.openmotics.status"/>
  </policy>

  <policy user="root">
    <allow send_destination="com.openmotics.status"/>
    <allow receive_sender="com.openmotics.status"/>
  </policy>

</busconfig>
EOF

rm /etc/localtime
cp /usr/share/zoneinfo/UTC /opt/openmotics/etc/timezone
ln -s /opt/openmotics/etc/timezone /etc/localtime

mount -o remount,ro /

echo OpenMotics installed successfully