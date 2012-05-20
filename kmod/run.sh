#!/bin/bash

output=mntrace.txt
mod=mntracer.ko

trap "echo removing $mod; rmmod $mod; exit 0" SIGINT SIGTERM EXIT

rm $output
rmmod $mod
insmod ./$mod

while true; do
	dmesg -c >> $output;
	sleep .01
done
