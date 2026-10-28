"""Exercise the actual common init/exit code with counted native resources.

Runs in the WSL kernel-build environment; no device actions or MMIO access.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import sys

source = Path(sys.argv[1]).read_text()

def function(marker):
    start = source.find(marker)
    if start < 0:
        return ''
    brace = source.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

code = ''.join(function(marker) for marker in [
    'static bool qmp_combo_keep_inputs_on_reconfigure(',
    'static int qmp_combo_com_init(',
    'static int qmp_combo_com_exit(',
    'static int qmp_combo_usb_power_on(',
    'static int qmp_combo_usb_init(',
])
constants = sorted(set(re.findall(r'\b[A-Z][A-Z0-9_]+\b', code)))
provided = {'QMPPHY_MODE_USB3DP', 'QMPPHY_MODE_USB3_ONLY', 'QMPPHY_MODE_DP_ONLY',
            'TYPEC_ORIENTATION_REVERSE', 'PIPE', 'USB2', 'USB3'}
defines = ''.join(f'#define {name} 0\n' for name in constants if name not in provided)

stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define __iomem
typedef unsigned int u32;
enum { TYPEC_ORIENTATION_REVERSE=2 };
enum { QMPPHY_MODE_USB3DP, QMPPHY_MODE_USB3_ONLY, QMPPHY_MODE_DP_ONLY };
struct device { const char *name; };
struct qmp_phy_cfg { int num_vregs,num_resets; bool invert_cc_polarity,has_pwrdn_delay; unsigned regs[1];
 void *serdes_tbl,*tx_tbl,*rx_tbl,*pcs_tbl,*pcs_misc_tbl,*pcs_usb_tbl;
 int serdes_tbl_num,tx_tbl_num,rx_tbl_num,pcs_tbl_num,pcs_misc_tbl_num,pcs_usb_tbl_num; };
struct qmp_combo {
 struct device *dev; const struct qmp_phy_cfg *cfg;
 char *com,*pcs_aon,*pcs,*serdes,*tx,*tx2,*rx,*rx2,*pcs_misc,*pcs_usb;
 int init_count,orientation,qmpphy_mode,num_clks,usb_init_count,phy_mutex;
 void *vregs,*resets,*clks,*pipe_clk;
};
static int reg_refs,clock_refs,pipe_refs,acquires,drops,register_writes;
struct phy {struct qmp_combo *q;};
static int fail_phase,phase,resets,usb_error;
static bool gaokun=true;
static const char *dev_name(struct device *dev) { return dev->name; }
static bool of_machine_is_compatible(const char *name) {(void)name;return gaokun;}
#define dev_err(...) ((void)0)
static int acquire(int *refs) {
 if (++phase==fail_phase) return -EIO;
 ++*refs;++acquires;return 0;
}
static void release(int *refs) {assert(*refs>0);--*refs;++drops;}
static int regulator_bulk_enable(int n,void *r) {(void)n;(void)r;return acquire(&reg_refs);}
static void regulator_bulk_disable(int n,void *r) {(void)n;(void)r;release(&reg_refs);}
static int clk_bulk_prepare_enable(int n,void *c) {(void)n;(void)c;return acquire(&clock_refs);}
static void clk_bulk_disable_unprepare(int n,void *c) {(void)n;(void)c;release(&clock_refs);}
static int clk_prepare_enable(void *c) {(void)c;return acquire(&pipe_refs);}
static void clk_disable_unprepare(void *c) {(void)c;release(&pipe_refs);}
static int reset_control_bulk_assert(int n,void *r) {
 (void)n;(void)r;++resets;if (++phase==fail_phase)return -EIO;return 0;
}
static int reset_control_bulk_deassert(int n,void *r) {
 (void)n;(void)r;++resets;if (++phase==fail_phase)return -EIO;return 0;
}
static void qphy_setbits(char *p,int off,unsigned val) {(void)p;(void)off;(void)val;++register_writes;}
static void qphy_clrbits(char *p,int off,unsigned val) {(void)p;(void)off;(void)val;++register_writes;}
static void writel(unsigned val,char *p) {(void)val;(void)p;++register_writes;}
static void qmp_configure(struct device*d,char*p,void*t,int n) {(void)d;(void)p;(void)t;(void)n;}
static void qmp_configure_lane(struct device*d,char*p,void*t,int n,int lane) {(void)lane;qmp_configure(d,p,t,n);}
static void usleep_range(int a,int b) {(void)a;(void)b;}
static void *phy_get_drvdata(struct phy*p) {return p->q;}
static void mutex_lock(int*m) {assert(!*m);*m=1;}
static void mutex_unlock(int*m) {assert(*m);*m=0;}
#define readl_poll_timeout(addr,val,cond,interval,timeout) ((void)(addr),(void)(val),usb_error)
'''

tests = r'''
static struct device dev={"8903000.phy"};
static struct qmp_phy_cfg cfg={.num_vregs=2,.num_resets=2};
static char mmio[1];
static struct qmp_combo q;
static void setup(int count) {
 q=(struct qmp_combo){.dev=&dev,.cfg=&cfg,.init_count=count,.num_clks=3,
  .com=mmio,.pcs=mmio,.orientation=1,.qmpphy_mode=QMPPHY_MODE_USB3DP};
 dev.name="8903000.phy";gaokun=true;
 reg_refs=clock_refs=pipe_refs=count?1:0;
 acquires=drops=register_writes=fail_phase=phase=resets=usb_error=0;
}
static void owned(void) {assert(reg_refs==1&&clock_refs==1&&pipe_refs==1);}
static void empty(void) {assert(!reg_refs&&!clock_refs&&!pipe_refs);}
int main(void) {
 int mode,fail,r;struct phy phy={&q};
 /* A live reconfiguration resets/programs hardware without gating inputs. */
 for(mode=QMPPHY_MODE_USB3DP;mode<=QMPPHY_MODE_DP_ONLY;++mode) {
  setup(1);q.qmpphy_mode=mode;
  assert(!qmp_combo_com_exit(&q,true));owned();assert(!drops);
  assert(!qmp_combo_com_init(&q,true));owned();
  assert(!acquires&&!drops&&register_writes&&resets>=3&&q.init_count==1);
 }
 /* Forced reset failures retain all existing native ownership and count. */
 for(fail=1;fail<=2;++fail) {
  setup(1);fail_phase=fail;r=qmp_combo_com_init(&q,true);
  assert(r==-EIO);owned();assert(q.init_count==1&&!drops&&!acquires);
  fail_phase=0;assert(!qmp_combo_com_exit(&q,false));empty();assert(drops==3&&!q.init_count);
 }
 /* Ordinary consumer init/exit still owns exactly one shared set. */
 setup(0);assert(!qmp_combo_com_init(&q,false));owned();assert(q.init_count==1);
 assert(acquires==3);assert(!qmp_combo_com_exit(&q,false));empty();assert(!q.init_count);
 setup(1);assert(!qmp_combo_com_init(&q,false));owned();assert(q.init_count==2&&!acquires);
 assert(!qmp_combo_com_exit(&q,false));owned();assert(q.init_count==1&&!drops);
 assert(!qmp_combo_com_exit(&q,false));empty();
 /* Every acquisition/reset failure on ordinary init is balanced. */
 for(fail=1;fail<=5;++fail) {
  setup(0);fail_phase=fail;r=qmp_combo_com_init(&q,false);
  assert(r==-EIO);empty();assert(!q.init_count&&acquires==drops);
 }
 /* Primary USB/other machines retain their existing forced-cycle behavior. */
 setup(1);dev.name="88eb000.phy";
 assert(!qmp_combo_com_exit(&q,true));empty();assert(drops==3);
 assert(!qmp_combo_com_init(&q,true));owned();assert(acquires==3&&q.init_count==1);
 setup(1);gaokun=false;
 assert(!qmp_combo_com_exit(&q,true));empty();
 assert(!qmp_combo_com_init(&q,true));owned();
 /* Nonzero shared DP/USB count remains unchanged through forced changes. */
 setup(2);assert(!qmp_combo_com_exit(&q,true));owned();
 assert(!qmp_combo_com_init(&q,true));owned();assert(q.init_count==2&&!acquires&&!drops);
 /* A failed USB initialization returns all common-owned resources once. */
 setup(0);usb_error=-ETIMEDOUT;r=qmp_combo_usb_init(&phy);
 assert(r==-ETIMEDOUT&&!q.init_count&&!q.usb_init_count&&!q.phy_mutex);empty();assert(acquires==drops);
 /* A successful USB initialization retains common resources for later exit. */
 setup(0);assert(!qmp_combo_usb_init(&phy));owned();assert(q.init_count==1&&q.usb_init_count==1&&!q.phy_mutex);
 setup(1);usb_error=-ETIMEDOUT;assert(qmp_combo_usb_power_on(&phy)==-ETIMEDOUT);owned();
 assert(!qmp_combo_com_exit(&q,false));empty();assert(drops==3&&!q.init_count);
 setup(1);fail_phase=1;assert(qmp_combo_com_exit(&q,true)==-EIO);owned();assert(!drops&&q.init_count==1);
 fail_phase=0;assert(!qmp_combo_com_exit(&q,false));empty();assert(drops==3&&!q.init_count);
 setup(1);dev.name="88eb000.phy";assert(!qmp_combo_com_exit(&q,true));empty();
 phase=0;fail_phase=1;assert(qmp_combo_com_init(&q,true)==-EIO);empty();assert(!q.init_count);
 puts("PASS: 20 actual common-input/USB lifecycle/failure cases");
 return 0;
}
'''
if '--usb-error-only' in sys.argv:
    tests = tests[:tests.index('int main(void)')] + r'''
int main(void) {
 struct phy phy={&q};int ret;
 setup(0);usb_error=-ETIMEDOUT;ret=qmp_combo_usb_init(&phy);
 assert(ret==-ETIMEDOUT&&!q.init_count&&!q.usb_init_count&&!q.phy_mutex);
 empty();assert(acquires==drops);puts("PASS: failed USB init releases common ownership once");return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='qmp-common-input-') as directory:
    out = Path(directory) / 'harness.c'
    out.write_text(stub + defines + code + tests, encoding='utf-8')
    exe = str(out.with_suffix(''))
    subprocess.run(['gcc', '-std=gnu11', '-O2', '-Wall', str(out), '-o', exe], check=True)
    subprocess.run([exe], check=True)
