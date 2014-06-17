#!/bin/bash

## Set the system clock
echo server ntp.ubuntu.com > /etc/ntp.conf
killall ntpd
ntpd -q -g -x

## Install cherrypy
wget http://openmotics.com:8100/distro/CherryPy-3.2.2.tar.gz
wget http://openmotics.com:8100/distro/cherrypy-https.patch
tar xzf CherryPy-3.2.2.tar.gz
cd CherryPy-3.2.2
patch -p1 < ../cherrypy-https.patch
python setup.py build
python setup.py install
cd ..

## Install OpenVPN
wget http://openmotics.com:8100/distro/openvpn-2.2.2.tar.gz
tar xzf openvpn-2.2.2.tar.gz
cd openvpn-2.2.2
./configure --disable-lzo
make
make install
cd ..

## Install supervisord
wget http://openmotics.com:8100/distro/supervisor-3.0a12.tar.gz
wget http://openmotics.com:8100/distro/supervisor.init
wget http://openmotics.com:8100/distro/supervisord.conf

tar xzf supervisor-3.0a12.tar.gz
cd supervisor-3.0a12
python setup.py install
cd ..

mkdir /etc/supervisor/
mkdir /etc/supervisor/conf.d/
mkdir /var/log/supervisor/

mv supervisord.conf /etc/supervisord.conf
mv supervisor.init /etc/init.d/supervisor
chmod +x /etc/init.d/supervisor

for i in `seq 0 6`; do ln -s /etc/init.d/supervisor /etc/rc${i}.d/S99supervisor; done

## Install Qt packages
PACKAGES="libffi5_3.0.10-r0_armv7a.ipk libqtcore4_4.8.0-r48.1_armv7a.ipk libqtsql4_4.8.0-r48.1_armv7a.ipk qt4-plugin-sqldriver-sqlite_4.8.0-r48.1_armv7a.ipk"
for i in $PACKAGES; do wget http://openmotics.com:8100/distro/packages/${i}; done
opkg install $PACKAGES

## Configure filesystems
mkdir /opt

cat << EOF > /etc/fstab
rootfs               /                    auto       defaults,noatime,ro   1  1
proc                 /proc                proc       defaults              0  0
devpts               /dev/pts             devpts     mode=0620,gid=5       0  0
tmpfs                /tmp                 tmpfs      defaults              0  0
tmpfs                /var                 tmpfs      defaults              0  0
/dev/mmcblk0p3       /opt                 auto       defaults,noatime      1  1
EOF

## Make status display (i2c-2) accessible
mkdir /mnt/boot/
mount /dev/mmcblk0p1 /mnt/boot/
cat << EOF > /mnt/boot/uEnv.txt
optargs="run_hardware_tests i2c_bus=2,100 panic=10 softlockup_panic=1"
EOF
umount /mnt/boot/
rm -R /mnt/boot

## Remove unused kernel modules
rm /etc/modules-load.d/hidp.conf
rm /etc/modules-load.d/ircomm-tty.conf
rm /etc/modules-load.d/rfcomm.conf
/usr/sbin/update-modules

## Make the beagle bone automatically restart on kernel panic
cat << EOF >> /etc/sysctl.conf
kernel.panic = 10
kernel.panic_on_oops = 1 
kernel.hung_task_panic = 1
kernel.hung_task_timeout_secs = 300
kernel.unknown_nmi_panic = 1
kernel.panic_on_unrecovered_nmi = 1
kernel.panic_on_io_nmi = 1
EOF

## Instal Google public DNS name servers
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf


## Install ntpsync
cat << EOF > /usr/bin/ntpsync
#!/bin/bash
# Keep trying to ntpdate (1 minute interval), until the ntpdate is succesful.
# If the ntpdate fails, set the date to a default value.

SERVER=ntp.ubuntu.com
DEFAULT_DATE="2013-07-01 00:00"
SUCCESS_INTERVAL=3600
FAIL_INTERVAL=60

systemctl stop ntpd.service

echo "Started ntpsync."

while [ 1 ]; do
    echo "Starting ntpdate."
    ntpdate \$SERVER
    if [ x"\$?" == x"0" ]; then
        echo "ntpdate was succesfull."
        sleep \$SUCCESS_INTERVAL
    else
        echo "ntpdate failed."
        date | grep 2000 # Check if we are on the default date (1th of Jan 2000)
        if [ x"\$?" == x"0" ]; then
            echo "Setting date to \$DEFAULT_DATE"
            date -s "\$DEFAULT_DATE"
        fi
        sleep \$FAIL_INTERVAL
    fi
done
EOF

chmod +x /usr/bin/ntpsync

cat << EOF > /etc/supervisor/conf.d/ntpsync.conf 
[program:ntpsync]
command=/usr/bin/ntpsync
autostart=true
autorestart=true
startsecs=0
exitcodes=0
priority=1
EOF


## Install watchdog
cat << EOF > /usr/bin/watchdog.py
'''
Gives the watchdog a push every 10 seconds.

Created on Oct 24, 2012

@author: fryckbos
'''
import time

def main():
	watchdog = open('/dev/watchdog', 'w')

    while True:
        watchdog.write("O")
        watchdog.flush()
        
        time.sleep(10)
    
    
if __name__ == '__main__':
    main()
EOF

cat << EOF > /etc/supervisor/conf.d/watchdog.conf 
[program:watchdog]
command=python /usr/bin/watchdog.py
autostart=true
autorestart=false
priority=1
EOF


## Install BeagleBone Black device tree file
cp BBB/dts/am335x-boneblack.dtb /boot/

