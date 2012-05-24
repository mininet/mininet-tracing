import argparse
import re
from collections import namedtuple, defaultdict
import os
import matplotlib as m
#m.use("Agg")
from matplotlib import rc
import matplotlib.pyplot as plt
import colorsys

rc('legend', **{'fontsize': 'small'})

DEF_PLOTS = ['cpu', 'history', 'links']

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

parser.add_argument('--max-ms',
                    type=float,
                    default=1e6,
                    dest="max_ms")

parser.add_argument('--samples',
                    type=int,
                    default=0)

parser.add_argument('--start',
                    type=float,
                    default=None)

parser.add_argument('--end',
                    type=float,
                    default=None)

parser.add_argument('--duration',
                    type=float,
                    default=None)

parser.add_argument('--absolute',
                    action="store_true",
                    default=False)

parser.add_argument('--plots',
                    type=str,
                    default=None,
                    help="comma-sep list in [%s]" % ','.join(DEF_PLOTS))

parser.add_argument('--show',
                    type=bool,
                    default=False,
                    help="show plots?")

args = parser.parse_args()

if not args.plots:
    args.plots = DEF_PLOTS
else:
    args.plots = args.plots.split(',')
    for plot in args.plots:
        if plot not in DEF_PLOTS:
            raise Exception("unknown plot type: %s" % plot)

# For coloring scheduling histories:
COLOR_LIST = [c for c in 'bgrcmy']

FIXED_COLOR_MAP = {
    'h1': 'r',
    'h2': 'g',
    'r': 'b',
    'sysdefault': '#d0d0d0',
    '/' : '#b0b0b0'
}
USE_FIXED_COLOR_MAP = True

pat_sched = re.compile(r'(\d+.\d+): mn_sched_switch: cpu (\d+), prev: ([^,]+), next: ([^\s]+)')
pat_htb = re.compile(r'\[00(\d)\] (\d+.\d+): mn_htb: action: ([^\s]+), link: ([^\s]+), len: ([^\s]+)')

SchedData = namedtuple('SchedData', ['time', 'cpu', 'prev', 'next'])
HTBData = namedtuple('HTBData', ['cpu', 'time', 'action', 'link', 'qlen'])
ContainerInterval = namedtuple('ContainerInterval', ['start', 'duration', 'cpu'])

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

        delta = del_us(htbdata.time, self.last_dequeue)
        self.inter_dequeues.append(delta)
        self.last_dequeue = htbdata.time

class ContainerStats:
    def __init__(self):
        # Stats
        self.exectimes = []  # List of scheduled-in durations
        self.latency = []  # List of gaps between sched-out and next sched-in
        self.intervals = []  # List of ContainerInterval objects

        # State updated for each SchedData entry processed
        self.last_descheduled = None
        self.start_time = None
        self.name = ''
        self.cpu = None

    def schedule_in(self, sched_data):
        if self.name == '':
            self.name = sched_data.next
        assert(self.name == sched_data.next)

        if self.last_descheduled != None:
            latency = del_us(sched_data.time, self.last_descheduled)
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
            exectime_us = del_us(sched_data.time, self.start_time)
            self.exectimes.append(exectime_us)
            pi = ContainerInterval(start = float(self.start_time),
                                 duration = exectime_us * 1.0e-6,
                                 cpu = sched_data.cpu)
            self.intervals.append(pi)

        self.last_descheduled = sched_data.time
        self.start_time = None

    def summary(self):
        if self.exectimes:
            avg_exectime_us = avg(self.exectimes)
            print '     Execution time:   %5.3f us' % (avg_exectime_us)
        if self.latency:
            avg_latency_us = avg(self.latency)
            print '            Latency:   %5.3f us' % (avg_latency_us)
        if self.intervals:
            print '      Num Intervals:   %i' % len(self.intervals)
        return

class CPUStats:
    def __init__(self):
        self.cpu = None
        self.current_container = ''
        # Dict of container names to ContainerStats objects
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
    return HTBData(cpu=m.group(1),
                   time=m.group(2),
                   action=m.group(3),
                   link=m.group(4),
                   qlen=m.group(5))

def del_us(t1, t2):
    sec1, usec1 = map(int, t1.split('.'))
    sec2, usec2 = map(int, t2.split('.'))

    return abs((sec2 - sec1) * 10**6 + (usec2 - usec1))

def parse(f, args):

    def in_range(time_val, start, end, duration, start_time=0.0):
        """Return True if time is within range.

        If nothing is specified, filter nothing.
        If start is specified, filter before start.
        If end is specified, filter after end.
        If duration is specified, filter after start + duration.
        """

        # Make time relative to start of trace
        time_val -= start_time
        if start is not None:
            if time_val < start:
                return False
        if end is not None:
            if time_val > end:
                return False
        if duration is not None:
            if time_val > start + duration:
                return False
        return True

    stats = defaultdict(CPUStats)
    linkstats = defaultdict(LinkStats)
    start_time = None

    lineno = 0
    ignored_linenos = []

    if args.absolute:
        start_time = 0.0

    for l in open(f).xreadlines():
        lineno += 1
        # End early if samples param given at command line.
        if args.samples and lineno >= args.samples:
            break

        sched = parse_sched(l)
        htb = parse_htb(l)

        if start_time is None:
            if htb:
                start_time = float(htb.time)
            elif sched:
                start_time = float(sched.time)

        try:
            if htb:
                htb_time = float(htb.time)
                if in_range(htb_time, args.start, args.end, args.duration, start_time):
                    if htb.action == 'dequeue' and int(htb.qlen) > 0:
                        linkstats[htb.link].dequeue(htb)
                elif args.end and (htb_time - start_time > args.end):
                    break
                elif args.duration and (htb_time - start_time > (args.start + args.duration)):
                    break

            if sched:
                sched_time = float(sched.time)
                if in_range(sched_time, args.start, args.end, args.duration, start_time):
                    stats[sched.cpu].insert(sched)
                elif args.end and (sched_time - start_time> args.end):
                    break
                elif args.duration and (sched_time - start_time > (args.start + args.duration)):
                    break

        except:
            ignored_linenos.append(lineno)

    print 'Processed %d lines.' % lineno
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


def plot_link_stat(stats, prop, kind, outfile, metric, title=None):
    links = stats.keys()
    links.sort()

    if not links:
        print "WARNING: no link data, not generating figure %s." % outfile
        return

    fig = plt.figure(figsize=(len(links), 8))

    metric += ' (us)'

    xvalues = []
    for i, link in enumerate(links):
        if kind == 'CDF':
            x, y = cdf(getattr(stats[link], prop))
            plt.plot(x, y, lw=2, label=link)
            plt.xscale('log')
            plt.xlabel(metric)
        else:
            xvalues.append(getattr(stats[link], prop))

    if kind == 'boxplot':
        plt.boxplot(xvalues)
        plt.xticks(range(1, 1+len(links)), links)
        plt.yscale('log')
        plt.ylabel(metric)
    else:
        plt.legend(loc="lower right")

    if title is None:
        title = outfile
    plt.title(title)
    plt.grid(True)
    fig.autofmt_xdate()

    print outfile
    plt.savefig(outfile)
    if args.show:
        plt.show()

def plot_container_stat(kvs, kind, outfile, metric, title=None):
    exclude_keys = []
    keys = kvs.keys()
    keys.sort()

    fig = plt.figure(figsize=(len(keys), 8))

    l = len(keys)
    xvalues = []
    xlabels = []

    for i, k in enumerate(keys):
        if k in exclude_keys:
            continue

        ms_values = map(lambda us: us/1e3,
                        kvs[k])
        if kind == 'CDF':
            x, y = cdf(ms_values)

            hue = i*1.0/l
            plt.plot(x, y,
                     label=k,
                     lw=2,
                     color=colorsys.hls_to_rgb(hue, 0.5, 1.0))
        else:
            xvalues.append(ms_values)
            xlabels.append(k)

    plt.grid(True)
    metric += ' (ms)'
    if kind == 'boxplot':
        nx = len(xvalues)
        plt.boxplot(xvalues)
        plt.xticks(range(1,nx+1), xlabels)
        plt.yscale('log')
        plt.ylabel(metric)
        plt.ylim((0, args.max_ms))
    else:
        plt.xlabel(metric)
        plt.xlim((0, args.max_ms))
        plt.xscale('log')
        plt.ylabel("Fraction")
        plt.legend(loc="lower right")

    if title is None:
        title = outfile
    plt.title(title)
    fig.autofmt_xdate()

    print outfile
    plt.savefig(outfile)
    if args.show:
        plt.show()

WIDTH_SCALE_FACTOR = 20  # inches of figure per second of recording.

def plot_scheduling_history(containerstats, outfile, title = None, exts = ['pdf', 'png']):
    container_index = 0
    colors = {}  # Dict of container names to color strings

    if USE_FIXED_COLOR_MAP:
        colors = FIXED_COLOR_MAP
    # Grab the full list of containers to assign colors.
    for cpu, cpustats in containerstats.iteritems():
        for container, stats in cpustats.container_stats.iteritems():
            if container not in colors:
                colors[container] = COLOR_LIST[container_index]
                container_index += 1

    start_time = 1e10
    end_time = 0.0
    for cpu, cpustats in containerstats.iteritems():
        for container, stats in cpustats.container_stats.iteritems():
            start_time_candidate = stats.intervals[0].start
            if start_time_candidate < start_time:
                start_time = start_time_candidate
            end_time_candidate = stats.intervals[-1].start + stats.intervals[-1].duration
            if end_time_candidate > end_time:
                end_time = end_time_candidate

    elapsed = end_time - start_time
    print "Start: %0.2f, end: %0.2f, length: %0.4f" % (start_time, end_time, elapsed)

    # Plot a history of scheduling events, with one row per CPU.
    fig = plt.figure(figsize=(max(8, WIDTH_SCALE_FACTOR * elapsed), 8))
    ax = fig.add_subplot(111)
    for i, cpu in enumerate(sorted(containerstats.keys())):
        cpustats = containerstats[cpu]
        for container, stats in cpustats.container_stats.iteritems():
            bars = [(d.start, d.duration) for d in stats.intervals]
            ax.broken_barh(bars, (0.5 + i, 1), facecolors = colors[container],
                           label = container, linewidth = 0)

    numcpus = len(containerstats)
    ax.set_ylim(0, numcpus + 1)
    #ax.set_xlim(0,200)
    ax.set_xlabel('seconds')
    ax.set_yticks([1 + i for i in range(numcpus)])
    ax.set_yticklabels(['CPU %i' % (1 + i) for i in range(numcpus)])

    # TODO: make this work.
    #plt.legend( [c for c in colors.keys()], loc='right')

    if title is None:
        title = outfile
    plt.title(title)

    for ext in exts:
        print outfile + ' ' + ext
        plt.savefig(outfile + '.' + ext)
    if args.show:
        plt.show()

def plot(containerstats, linkstats):
    dir = args.odir
    kinds = ['CDF', 'boxplot']
    if not os.path.exists(dir):
        os.makedirs(dir)

    if 'cpu' in args.plots:
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
    if 'history' in args.plots:
        # plot history of scheduling on each core
        outfile = 'sched_history'
        outfile = os.path.join(args.odir, outfile)
        plot_scheduling_history(containerstats, outfile)

    if 'links' in args.plots:
        # plot all links' inter-dequeue times
        for kind in kinds:
            for prop in ['inter_dequeues']:
                outfile = 'link-%s-%s.png' % (prop, kind)
                outfile = os.path.join(args.odir, outfile)
                plot_link_stat(linkstats,
                               prop,
                               kind, outfile, metric=prop)
    return

containerstats, linkstats = parse(args.file, args)
plot(containerstats, linkstats)
