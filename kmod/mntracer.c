
#include <linux/module.h>
#include <linux/sched.h>
#include <linux/cgroup.h>
#include <linux/fs.h>
#include <linux/net.h>
#include <linux/kernel.h>
#include <linux/slab.h>
#include <linux/proc_fs.h>
#include <linux/ktime.h>
#include <linux/time.h>
#include <net/net_namespace.h>

#define CREATE_TRACE_POINTS
#include "mntracer.h"

static inline const char *get_cgroup_name(struct task_struct *tsk) {
    struct css_set *css;
    struct cgroup_subsys_state *subsys;
    struct cgroup *cg;
    struct dentry *dentry;

    css = tsk->cgroups;
    if(!css)
        return NULL;

    /* TODO: Check how subsys's are populated, so we know if subsys[1]
       is what we want.  I think it's the CPU cgroup. */
    subsys = css->subsys[1];
    if(!subsys)
        return NULL;

    cg = subsys->cgroup;
    if(!cg)
        return NULL;

    dentry = cg->dentry;
    if(!dentry)
        return NULL;

    return dentry->d_name.name;
}

static void probe_sched_switch(void *ignore,
                               struct task_struct *prev, struct task_struct *next)
{
    const char *old, *new;

    old = get_cgroup_name(prev);
    new = get_cgroup_name(next);

    /* This is a filtered event trace, so we can use ftrace in sysfs
       to count these events */
    if(old != new) {
        trace_mn_sched_switch(smp_processor_id(), old, new);
    }
}

static int __init mntracer_init(void)
{
	int ret;

	ret = register_trace_sched_switch(probe_sched_switch, NULL);
	WARN_ON(ret);
	return 0;
}

static void __exit mntracer_exit(void)
{
	unregister_trace_sched_switch(probe_sched_switch, NULL);
	tracepoint_synchronize_unregister();
}

module_init(mntracer_init);
module_exit(mntracer_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Mininet");
MODULE_DESCRIPTION("Mininet tracing");
