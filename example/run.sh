#!/bin/bash

source ../trace.sh
exptid=`date +%b%d-%H:%M`

if [ "$UID" != "0" ]; then
    warn "Please run as root"
    exit 0
fi


finish() {
	# Re-enable all cores
	./mod-cores.sh

	# Clean up
	killall -9 python iperf
	mn -c

	exit
}

trap finish SIGINT


clean_text_files () {
    # Remove random output character in the text file
    dir=${1:-/tmp}
    pushd $dir
    mkdir -p clean
    for f in *.txt; do
        echo "Cleaning $f"
        cat $f | tr -d '\001' > clean/$f
    done
    popd
}

# Compile module, insert mntracer, etc.
trace_init

# proto = tcp, udp
# n = number of switches
# P = parallel instantiations of the topology
# cpu = # active CPUs during the test
for cpu in 1; do
for proto in tcp; do
for bw in 10 100; do
for n in 0 1 10; do
for P in 1; do
    dir=$exptid/bw$bw-n$n-proto$proto-P$P-cpu$cpu
    mkdir -p $dir

    ./mod-cores.sh $cpu

    # Start the experiment
    trace_start $dir/mntrace
    python LineTopo.py -n $n --bw $bw --dir $dir -t 20 --proto $proto -p $P
    trace_stop $dir/mntrace
    grep mn_ $dir/mntrace > $dir/mntrace_trimmed

	# Enable more cores for plotting.
	# WARNING: repeatedly enabling/disabling cores causes mod-cores.sh
	# to hang.  So, don't use it unless it works on your system.
	# ./mod-cores.sh

    # Start plotting both zoomed in and non-zoomed in version of plots
    python ../parse.py -f $dir/mntrace_trimmed --odir $dir/plots --plots links,cpu,history  \
        --start 10.0 \
        --duration 1.0 &
    python ../parse.py -f $dir/mntrace_trimmed --odir $dir/plots_full --plots links,cpu,history &
    clean_text_files $dir
    wait
done
done
done
done
done

finish
