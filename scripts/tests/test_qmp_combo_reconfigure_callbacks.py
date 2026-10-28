"""Check actual V2 callbacks for mode handling and native error propagation."""
from pathlib import Path
import subprocess
import tempfile
import sys

source = Path(sys.argv[1]).read_text()

def function(marker):
    start = source.index(marker)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

from qmp_combo_test_support import CALLBACK_STUB

stub = CALLBACK_STUB
stub = stub.replace('static int enables,', 'static int native_calls,fail_stage;\nstatic int enables,', 1)
stub = stub.replace('bool dp_powered_on;', 'bool dp_powered_on,typec_reconfigure_failed;', 1)
stub = stub.replace('static void event(void) {hardware++;if(guard_expected)assert(refs==1);}',
    'static void event(void) {hardware++;}\nstatic int native_step(void) {return ++native_calls==fail_stage ? -EIO : 0;}')
for name, args in [
    ('qmp_combo_usb_power_on', 'void*p'),
    ('qmp_combo_com_exit', 'struct qmp_combo*q,bool f'),
    ('qmp_combo_com_init', 'struct qmp_combo*q,bool f'),
]:
    old = f'static void {name}({args}) '
    assert old in stub
    start = stub.index(old)
    end = stub.index('\n', start)
    line = stub[start:end].replace('static void ', 'static int ', 1)
    line = line[:-1] + 'return native_step();}'
    stub = stub[:start] + line + stub[end:]

code = ''.join(function(x) for x in ['static int qmp_combo_typec_switch_set(',
                                     'static int qmp_combo_typec_mux_set('])
tests = r'''
static struct device dev={"8903000.phy"};
static struct qmp_phy_cfg cfg={aux};
static struct qmp_combo q;
static struct typec_switch_dev sw={&q};
static struct typec_mux_dev mux={&q};
static struct alt dp={USB_TYPEC_DP_SID};
static void reset(void) {
 q=(struct qmp_combo){.dev=&dev,.cfg=&cfg,.init_count=1,.usb_init_count=1,
  .orientation=NORMAL,.qmpphy_mode=QMPPHY_MODE_USB3DP};
 enables=disables=refs=hardware=clock_error=native_calls=fail_stage=0;
}
static void done(void) {assert(!q.phy_mutex&&!refs&&!enables&&!disables);}
int main(void) {
 struct typec_mux_state state={0};int fail,r;
 reset();assert(!qmp_combo_typec_switch_set(&sw,REVERSE));assert(q.orientation==REVERSE&&native_calls==3);done();
 reset();assert(!qmp_combo_typec_switch_set(&sw,NORMAL));assert(!hardware);done();
 reset();assert(!qmp_combo_typec_switch_set(&sw,TYPEC_ORIENTATION_NONE));assert(!hardware);done();
 reset();q.init_count=0;assert(!qmp_combo_typec_switch_set(&sw,REVERSE));assert(q.orientation==REVERSE&&!hardware);done();
 for(fail=1;fail<=3;++fail) {
  reset();fail_stage=fail;r=qmp_combo_typec_switch_set(&sw,REVERSE);
  assert(r==-EIO&&native_calls==fail&&q.orientation==NORMAL&&q.init_count==1&&q.usb_init_count==1);done();
 }
 reset();assert(!qmp_combo_typec_mux_set(&mux,&state));assert(q.qmpphy_mode==QMPPHY_MODE_USB3_ONLY&&native_calls==3);done();
 reset();q.qmpphy_mode=QMPPHY_MODE_USB3_ONLY;assert(!qmp_combo_typec_mux_set(&mux,&state));assert(!hardware);done();
 reset();q.dp_powered_on=true;assert(!qmp_combo_typec_mux_set(&mux,&state));assert(!hardware);done();
 reset();q.init_count=0;assert(!qmp_combo_typec_mux_set(&mux,&state));assert(q.qmpphy_mode==QMPPHY_MODE_USB3_ONLY&&!hardware);done();
 for(fail=1;fail<=3;++fail) {
  reset();fail_stage=fail;r=qmp_combo_typec_mux_set(&mux,&state);
  assert(r==-EIO&&native_calls==fail&&q.qmpphy_mode==QMPPHY_MODE_USB3DP&&q.init_count==1&&q.usb_init_count==1);done();
 }
 reset();state.alt=&dp;state.mode=TYPEC_DP_STATE_C;assert(!qmp_combo_typec_mux_set(&mux,&state));
 assert(q.qmpphy_mode==QMPPHY_MODE_DP_ONLY&&!q.usb_init_count&&native_calls==2);done();
 reset();q.qmpphy_mode=QMPPHY_MODE_DP_ONLY;q.usb_init_count=0;state.alt=0;
 assert(!qmp_combo_typec_mux_set(&mux,&state));assert(q.usb_init_count==1&&native_calls==3);done();
 for(fail=1;fail<=3;++fail) {
  reset();q.qmpphy_mode=QMPPHY_MODE_DP_ONLY;q.usb_init_count=0;fail_stage=fail;
  assert(qmp_combo_typec_mux_set(&mux,&state)==-EIO);
  assert(q.qmpphy_mode==QMPPHY_MODE_DP_ONLY&&!q.usb_init_count&&native_calls==fail);done();
 }
 reset();q.qmpphy_mode=QMPPHY_MODE_DP_ONLY;q.usb_init_count=0;
 assert(!qmp_combo_typec_switch_set(&sw,REVERSE));assert(native_calls==2);done();
 for(fail=1;fail<=3;++fail) {
  reset();fail_stage=fail;assert(qmp_combo_typec_switch_set(&sw,REVERSE)==-EIO);
  assert(q.typec_reconfigure_failed);fail_stage=0;r=native_calls;
  assert(!qmp_combo_typec_switch_set(&sw,NORMAL));
  assert(native_calls==r+3&&!q.typec_reconfigure_failed&&q.orientation==NORMAL);done();
 }
 for(fail=1;fail<=3;++fail) {
  reset();state.alt=0;fail_stage=fail;assert(qmp_combo_typec_mux_set(&mux,&state)==-EIO);
  assert(q.typec_reconfigure_failed);fail_stage=0;r=native_calls;state.alt=&dp;state.mode=TYPEC_DP_STATE_D;
  assert(!qmp_combo_typec_mux_set(&mux,&state));
  assert(native_calls==r+3&&!q.typec_reconfigure_failed&&q.qmpphy_mode==QMPPHY_MODE_USB3DP);done();
 }
 reset();fail_stage=2;assert(qmp_combo_typec_switch_set(&sw,REVERSE)==-EIO);fail_stage=0;r=native_calls;
 state.alt=&dp;state.mode=TYPEC_DP_STATE_D;assert(!qmp_combo_typec_mux_set(&mux,&state));
 assert(native_calls==r+3&&!q.typec_reconfigure_failed);done();
 reset();state.alt=0;fail_stage=3;assert(qmp_combo_typec_mux_set(&mux,&state)==-EIO);fail_stage=0;r=native_calls;
 assert(!qmp_combo_typec_switch_set(&sw,NORMAL));assert(native_calls==r+3&&!q.typec_reconfigure_failed);done();
 reset();fail_stage=1;assert(qmp_combo_typec_switch_set(&sw,REVERSE)==-EIO);r=native_calls;
 assert(!qmp_combo_typec_switch_set(&sw,TYPEC_ORIENTATION_NONE));assert(native_calls==r&&q.typec_reconfigure_failed);done();
 reset();q.typec_reconfigure_failed=true;q.dp_powered_on=true;state.alt=0;
 assert(qmp_combo_typec_mux_set(&mux,&state)==-EBUSY);assert(!hardware&&q.typec_reconfigure_failed);done();
 reset();q.typec_reconfigure_failed=true;q.dp_powered_on=true;
 assert(qmp_combo_typec_switch_set(&sw,NORMAL)==-EBUSY);assert(!hardware&&q.typec_reconfigure_failed);done();
 reset();q.typec_reconfigure_failed=true;q.dp_powered_on=true;
 assert(qmp_combo_typec_switch_set(&sw,REVERSE)==-EBUSY);assert(!hardware&&q.typec_reconfigure_failed);done();
 reset();state.alt=0;fail_stage=3;assert(qmp_combo_typec_mux_set(&mux,&state)==-EIO);r=hardware;
 q.dp_powered_on=true;fail_stage=0;assert(qmp_combo_typec_switch_set(&sw,NORMAL)==-EBUSY);
 assert(hardware==r&&q.typec_reconfigure_failed);done();
 reset();q.qmpphy_mode=QMPPHY_MODE_USB3_ONLY;q.typec_reconfigure_failed=true;q.dp_powered_on=true;state.alt=0;
 assert(qmp_combo_typec_mux_set(&mux,&state)==-EBUSY);assert(!hardware&&q.typec_reconfigure_failed);done();
 reset();q.qmpphy_mode=QMPPHY_MODE_USB3_ONLY;q.typec_reconfigure_failed=true;q.dp_powered_on=true;
 state.alt=&dp;state.mode=TYPEC_DP_STATE_C;
 assert(qmp_combo_typec_mux_set(&mux,&state)==-EBUSY);assert(!hardware&&q.typec_reconfigure_failed);done();
 puts("PASS: 35 actual callback mode/error/retry cases");return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='qmp-callback-') as directory:
    out = Path(directory) / 'harness.c'
    out.write_text(stub + code + tests, encoding='utf-8')
    exe = str(out.with_suffix(''))
    subprocess.run(['gcc', '-std=gnu11', '-O2', str(out), '-o', exe], check=True)
    subprocess.run([exe], check=True)
