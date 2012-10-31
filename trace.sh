#!/bin/bash

warn() {
	# Echo the provided command in color text.
	yellow='\e[0;33m' # Yellow
	reset='\e[0m'
	echo="echo -e"
	$echo "${yellow}$1${reset}"
}

trace_init() {
	# Call this function before running any tracing code
	dir=$(dirname $(readlink -f ${BASH_SOURCE[0]}))

	# Compile+Insert the modified HTB
	pushd $dir/htb
	make
	if [ $? -ne 0 ]; then
		warn "Failed to compile traced HTB module.  Please check."
		exit 0
	fi

	rmmod sch_htb; insmod ./sch_htb.ko;
	popd

	# Compile+Insert the tracer
	pushd $dir/kmod
	make
	if [ $? -ne 0 ]; then
		warn "Failed to compile tracing module.  Please check."
		exit 0
	fi

	rmmod mntracer; insmod ./mntracer.ko;
	popd
}


trace_start() {
	# argument: path to save the trace output
	traceoutput=${1-/tmp/mntrace}
	pushd /sys/kernel/debug/tracing

	# Enable ALL mininet events
	echo 1 > events/mininet/enable

	# Other events of interest
	for event in softirq_{raise,entry,exit}; do
		echo 1 > events/irq/$event/enable
	done

	# Enable tracing
	echo 1 > tracing_enabled
	echo 0 > tracing_on
	echo 1 > tracing_on

	popd

	mkdir -p $(dirname $traceoutput)
	warn "Writing trace to $traceoutput"
	(cat /sys/kernel/debug/tracing/trace_pipe > $traceoutput &)
}


trace_stop() {
	pushd /sys/kernel/debug/tracing
	echo 0 > events/mininet/enable
	echo 0 > tracing_on
	echo 0 > tracing_enabled
	warn "Finishing trace"
	((cat trace_pipe > /dev/null &); sleep 5; killall -9 cat;)
	wait
	popd
}


trace_plot() {
	# argument: pass the path to saved trace output
	mntrace=$1
	# Grab location of this script; leverage assumption that parse.py is in
	# the same dir to make it easier to call this function.
	# Trick from:
	# http://www.cyberciti.biz/faq/unix-linux-script-sourced-by-bash-can-it-determine-its-own-location/
	this_script_loc="${BASH_SOURCE[0]}"
	this_script_dir="${this_script_loc%/*}"
	parse=$this_script_dir/parse.py
	traceoutput=$mntrace
	python $parse -f $traceoutput --odir $(dirname $traceoutput)/plots
}
