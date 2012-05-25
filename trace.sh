#!/bin/bash

trace_start() {
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
    echo "Writing trace to $traceoutput"
    (cat /sys/kernel/debug/tracing/trace_pipe > $traceoutput &)
}


trace_stop() {
  pushd /sys/kernel/debug/tracing
  echo 0 > events/mininet/enable
  echo 0 > tracing_on
  echo 0 > tracing_enabled
  echo "Finishing trace"
  ((cat trace_pipe > /dev/null &); sleep 5; killall -9 cat;)
  wait
  popd
}

