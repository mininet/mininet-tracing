import argparse
import re
from collections import namedtuple, defaultdict
import os
import matplotlib as m
m.use("Agg")
from matplotlib import rc
import matplotlib.pyplot as plt
import colorsys

rc('legend', **{'fontsize': 'small'})

parser = argparse.ArgumentParser()
parser.add_argument('-f',
                    required=True,
                    dest="file")

parser.add_argument('--cpu',
                    default='*',
                    dest="cpu")

parser.add_argument('--action',
                    default='*',
                    dest="action")

parser.add_argument('--odir',
                    default='.',
                    dest="odir")

args = parser.parse_args()

pat_sched = re.compile(r'(\d+.\d+)  cpu: (\d+), prev: ([^,]+), next: ([^\s]+)')
pat_htb = re.compile(r'(ENQUEUE|DEQUEUE|OFBUF) time (\d+.\d+) src ([\d\.]+)  dst ([\d\.]+)')

SchedData = namedtuple('SchedData', ['time', 'cpu', 'prev', 'next'])
HTBData = namedtuple('HTBData', ['action', 'time', 'src', 'dst'])

def avg(lst):
    return sum(lst) * 1.0 / len(lst)

class LinkStats:
    def __init__(self):
        self.last_dequeue = None
        self.inter_dequeues = []

    def dequeue(self, htbdata):
        if self.last_dequeue is None:
            self.last_dequeue = htbdata.time
            return

        delta = del_ns(htbdata.time, self.last_dequeue)
        self.inter_dequeues.append(delta)
        self.last_dequeue = htbdata.time

class ContainerStats:
    def __init__(self):
        self.exectimes = []
        self.latency = []
        self.last_descheduled = None
        self.start_time = None
        self.name = ''
        self.cpu = None

    def schedule_in(self, sched_data):
        if self.name == '':
            self.name = sched_data.next
        assert(self.name == sched_data.next)

        if self.last_descheduled != None:
            latency = del_ns(sched_data.time, self.last_descheduled)
            self.latency.append(latency)

        if 0:
            # This sometimes happens when the trace claims that a
            # process has been scheduled in, even before the previous
            # one is scheduled out.  Right now, we ignore this data.
            # It could mean that the previous process yielded cpu to
            # another container that got scheduled in through some
            # other function (other than sched_switch)

            # Example:
            # cpu 0: prev: /, next: default
            # cpu 0: prev: /, next: default

            assert(self.start_time == None)

        self.start_time = sched_data.time
        return

    def schedule_out(self, sched_data):
        if self.name != '':
            assert(self.name == sched_data.prev)
        else:
            self.name = sched_data.prev

        if self.start_time is not None:
            exectime = del_ns(sched_data.time, self.start_time)
            self.exectimes.append(exectime)

        self.last_descheduled = sched_data.time
        self.start_time = None

    def summary(self):
        avg_latency_ns = avg(self.latency)
        avg_exectime_ns = avg(self.exectimes)
        print '     Execution time:   %5.3f us' % (avg_exectime_ns / 1000.0)
        print '            Latency:   %5.3f us' % (avg_latency_ns / 1000.0)
        return

class CPUStats:
    def __init__(self):
        self.cpu = None
        self.current_container = ''
        self.container_stats = defaultdict(ContainerStats)

    def insert(self, sched_data):
        if self.cpu is None:
            self.cpu = sched_data.cpu
        assert(self.cpu == sched_data.cpu)

        self.container_stats[sched_data.prev].cpu = sched_data.cpu
        self.container_stats[sched_data.next].cpu = sched_data.cpu

        self.container_stats[sched_data.prev].schedule_out(sched_data)
        self.container_stats[sched_data.next].schedule_in(sched_data)

    def summary(self):
        containers = self.container_stats.keys()
        containers.sort()
        print 'Container(s) seen: %s' % ','.join(containers)
        for k in containers:
            stats = self.container_stats[k]
            print '   Container %5s' % k
            stats.summary()
            print ''
        return

    def get(self, prop):
        ret = {}
        containers = self.container_stats.keys()
        for k in containers:
            ret[k] = getattr(self.container_stats[k], prop)
        return ret

def parse_sched(line):
    m = pat_sched.search(line)
    if not m:
        return None
    return SchedData(time=m.group(1),
                     cpu=m.group(2),
                     prev=m.group(3),
                     next=m.group(4))

def parse_htb(line):
    m = pat_htb.search(line)
    if not m:
        return None
    return HTBData(action=m.group(1),
                   time=m.group(2),
                   src=m.group(3),
                   dst=m.group(4))

def del_ns(t1, t2):
    sec1, nsec1 = map(int, t1.split('.'))
    sec2, nsec2 = map(int, t2.split('.'))

    return abs((sec2 - sec1) * 10**9 + (nsec2 - nsec1))

def parse(f):
    stats = defaultdict(CPUStats)
    linkstats = LinkStats()

    lineno = 0
    ignored_linenos = []

    for l in open(f).xreadlines():
        lineno += 1
        sched = parse_sched(l)
        htb = parse_htb(l)

        try:
            if htb:
                if htb.action == 'DEQUEUE':
                    linkstats.dequeue(htb)

            if sched:
                stats[sched.cpu].insert(sched)
        except:
            ignored_linenos.append(lineno)

    print 'Ignored %d lines: %s' % (len(ignored_linenos), ignored_linenos)
    for cpu in sorted(stats.keys()):
        print 'CPU: %s' % cpu
        stats[cpu].summary()
        print '-' * 80
    return stats, linkstats

def cdf(values):
    values.sort()
    prob = 0
    l = len(values)
    x, y = [], []

    for v in values:
        prob += 1.0 / l
        x.append(v)
        y.append(prob)

    return (x, y)


def plot_link_stat(stats, kind, outfile, metric, title=None):
    # TODO: Extend tracer to trace ALL dequeues in the system, and
    # hence plot this for all links
    plt.figure()

    # Convert from ns to us
    stats = map(lambda ns: ns/1e3, stats)
    metric += ' (us)'

    if kind == 'CDF':
        x, y = cdf(stats)
        plt.plot(x, y, lw=2)
        plt.xscale('log')
        plt.xlabel(metric)
    else:
        plt.boxplot(stats)
        plt.xticks([1], "link")
        plt.yscale('log')
        plt.ylabel(metric)
    plt.grid(True)

    if title:
        plt.title(title)

    print outfile
    plt.savefig(outfile)

def plot_container_stat(kvs, kind, outfile, metric, title=None):
    exclude_keys = []
    keys = kvs.keys()
    keys.sort()

    plt.figure()
    l = len(keys)
    xvalues = []
    xlabels = []

    for i, k in enumerate(keys):
        if k in exclude_keys:
            continue

        us_values = map(lambda ns: ns/1e6,
                        kvs[k])
        if kind == 'CDF':
            x, y = cdf(us_values)

            hue = i*1.0/l
            plt.plot(x, y,
                     label=k,
                     lw=2,
                     color=colorsys.hls_to_rgb(hue, 0.5, 1.0))
        else:
            xvalues.append(us_values)
            xlabels.append(k)

    plt.grid(True)
    metric += ' (ms)'
    if kind == 'boxplot':
        nx = len(xvalues)
        plt.boxplot(xvalues)
        plt.xticks(range(1,nx+1), xlabels)
        plt.yscale('log')
        plt.ylabel(metric)
    else:
        plt.xlabel(metric)
        plt.xscale('log')
        plt.ylabel("Fraction")
        plt.legend(loc="lower right")

    if title is None:
        title = outfile
    plt.title(title)

    print outfile
    plt.savefig(outfile)

def plot(containerstats, linkstats):
    dir = args.odir
    kinds = ['CDF', 'boxplot']
    if not os.path.exists(dir):
        os.makedirs(dir)

    # plot cpuX-{exectimes,latency}-{CDF,boxplot}
    for cpu in sorted(containerstats.keys()):
        cpustats = containerstats[cpu]

        for kind in kinds:
            for prop in ['exectimes', 'latency']:
                outfile = 'cpu%s-%s-%s.png' % (cpu, prop, kind)
                outfile = os.path.join(args.odir, outfile)
                plot_container_stat(cpustats.get(prop),
                                    kind,
                                    outfile,
                                    metric=prop)

    # plot specific link's inter-dequeue time
    for kind in kinds:
        for prop in ['inter_dequeues']:
            outfile = 'link-%s-%s.png' % (prop, kind)
            outfile = os.path.join(args.odir, outfile)
            plot_link_stat(getattr(linkstats, prop),
                           kind, outfile, metric=prop)
    return

containerstats, linkstats = parse(args.file)
plot(containerstats, linkstats)
