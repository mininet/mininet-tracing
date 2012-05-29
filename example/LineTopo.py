#!/usr/bin/python
import sys

from mininet.topo import Topo#, Node, Edge
from mininet import node
from mininet.net import Mininet

from mininet.cli import CLI
from mininet.log import lg
import os
from time import sleep

from mininet.node import CPULimitedHost
from mininet.link import TCLink

from subprocess import Popen, PIPE
import re
from time import sleep, time
import multiprocessing
import termcolor as T
import argparse

parser = argparse.ArgumentParser(description="Token bucket tester (line topology)")
parser.add_argument('--bw', '-B',
                    dest="bw",
                    action="store",
                    help="Bandwidth of links",
                    required=True)

parser.add_argument('--dir', '-d',
                    dest="dir",
                    action="store",
                    help="Directory to store outputs",
                    required=True)

parser.add_argument('-n',
                    dest="n",
                    action="store",
                    help="Number of switches in line.  Must be >= 1",
                    required=True)

parser.add_argument('-p', '--parallel',
                    dest="parallel",
                    action="store",
                    help="Number of parallel LineTopo instances.  Must be >= 1",
                    default=1)

parser.add_argument('-c', '--cpu',
                    dest="cpu",
                    action="store",
                    help="CPU b/w limiting for each node. -1 means no limits.",
                    default=-1)

parser.add_argument('-t',
                    dest="t",
                    action="store",
                    help="Seconds to run the experiment",
                    default=30)

parser.add_argument('--proto',
                    dest="proto",
                    choices=["tcp","udp"],
                    default="tcp")

parser.add_argument('--use-hfsc',
                    dest="use_hfsc",
                    action="store_true",
                    help="Use HFSC qdisc",
                    default=False)

parser.add_argument('--maxq',
                    dest="maxq",
                    action="store",
                    help="Max buffer size of each interface",
                    default=1000)

parser.add_argument('--speedup-bw',
                    dest="speedup_bw",
                    action="store",
                    help="Speedup bw for switch interfaces",
                    default=-1)

parser.add_argument('--use-bridge', '-b',
                    dest="use_bridge",
                    action="store_true",
                    help="Use Linux Bridge instead of OVSK",
                    default=False)

parser.add_argument('--one-switch',
                    dest="one_switch",
                    action="store_true",
                    help="Use single switch, instead of multiple switches",
                    default=False)

parser.add_argument('--static-cpu',
                    dest="static_cpu",
                    action="store_true",
                    help="Use static round robin CPU allocation",
                    default=False)

args = parser.parse_args()
args.n = int(args.n)
args.parallel = max(1, int(args.parallel))
args.cpu = int(args.cpu)

args.bw = float(args.bw)
if args.speedup_bw == -1:
    args.speedup_bw = args.bw

# Create output dir if needed:
if not os.path.exists(args.dir):
    os.makedirs(args.dir)

# Use Linux Bridge (interesting)
if args.use_bridge:
    from mininet.node import Bridge as Switch
else:
    from mininet.node import OVSKernelSwitch as Switch

lg.setLogLevel('info')

# It's no more a LineTopo, but let me not rename it
class LineTopo(Topo):

    def __init__(self, n=1, bw=100):
        # Add default members to class.
        super(LineTopo, self ).__init__()

        # Create template host, switch, and link
        host = dict(cpu=args.cpu, in_namespace=True)
        link = dict(bw=bw, delay='0.0ms', max_queue_size=int(args.maxq), speedup=float(args.speedup_bw), use_hfsc=args.use_hfsc)

        print '~~~~~~~~~~~~~~~~~> BW = %s' % bw
        hosts = []

        for p in xrange(args.parallel):
            # Create switch and host nodes
            h1 = self.add_host('h%d' % (2*p+1), **host)
            h2 = self.add_host('h%d' % (2*p+2), **host)
            hosts.append(h1)
            hosts.append(h2)

            if not args.one_switch:
                switches = []
                for i in xrange(n):
                    sw = self.add_switch( 'sw%d-%d' % (p,i) )
                    switches.append(sw)

                if len(switches):
                    self.add_link(h1, switches[0],  **link)
                    self.add_link(h2, switches[-1], **link)
                else:
                    self.add_link(h1, h2, **link)

                for i in xrange(0, n-1):
                    self.add_link(switches[i], switches[i+1], **link)

        if args.one_switch:
            sw = self.add_switch('sw0')
            for h in hosts:
                self.add_link(h, sw, **link)

def progress(t):
    while t > 0:
        print T.colored('  %3d seconds left  \r' % (t), 'cyan'),
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print '\r\n'

def main():
    seconds = int(args.t)
    topo = LineTopo(n=args.n, bw=args.bw)
    net = Mininet(topo=topo,switch=Switch, host=CPULimitedHost, link=TCLink)
    net.start()
    h1 = net.getNodeByName('h1')
    h2 = net.getNodeByName('h2')
    h1.sendCmd('ifconfig')
    h1.waitOutput()
    for p in xrange(args.parallel):
        h2 = net.getNodeByName('h%d' % (2*p+2))
        h2.sendCmd('iperf -s')
    clients = []
    for p in xrange(args.parallel):
        h1 = net.getNodeByName('h%d' % (2*p+1))
        h2 = net.getNodeByName('h%d' % (2*p+2))
        if args.proto == "udp":
            cmd = 'iperf -c %s -t %d -i 1 -u -b %sM > %s/iperf_%s.txt' % (h2.IP(), seconds, args.bw, args.dir, 'h%d' % (2*p+1))
        else:
            cmd = 'iperf -c %s -t %d -i 1 > %s/iperf_%s.txt' % (h2.IP(), seconds, args.dir, 'h%d' % (2*p+1))
        h1.sendCmd(cmd)

    progress(seconds)
    #CLI(net)
    Popen("killall -9 top bwm-ng", shell=True).wait()
    net.stop()

if __name__ == '__main__':
    main()
