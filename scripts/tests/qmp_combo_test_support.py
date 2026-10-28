"""Peripheral API doubles for the actual QMP combo callback bodies."""

CALLBACK_STUB = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
enum typec_orientation { TYPEC_ORIENTATION_NONE, NORMAL, REVERSE };
enum qmpphy_mode { QMPPHY_MODE_USB3DP, QMPPHY_MODE_USB3_ONLY, QMPPHY_MODE_DP_ONLY };
#define USB_TYPEC_DP_SID 0xff01
#define TYPEC_DP_STATE_C 1
#define TYPEC_DP_STATE_D 2
#define TYPEC_DP_STATE_E 3
#define TYPEC_DP_STATE_F 4
#define DP_PHY_PD_CTL_PSR_PWRDN 1
#define QSERDES_DP_PHY_PD_CTL 0
struct device { const char *name; };
struct qmp_combo;
struct qmp_phy_cfg { void (*dp_aux_init)(struct qmp_combo*); };
struct qmp_combo { struct device *dev; const struct qmp_phy_cfg *cfg;
 int phy_mutex,init_count,usb_init_count,dp_init_count; bool dp_powered_on;
 enum typec_orientation orientation; enum qmpphy_mode qmpphy_mode;
 void *pipe_clk,*usb_phy; char *dp_dp_phy; };
struct typec_switch_dev { struct qmp_combo *q; };
struct typec_mux_dev { struct qmp_combo *q; };
struct alt { unsigned svid; };
struct typec_mux_state { struct alt *alt; int mode; };
static int enables,disables,refs,hardware,clock_error,guard_expected;
static bool gaokun=true;
static const char *dev_name(struct device*d) {return d->name;}
static bool of_machine_is_compatible(const char*n) {(void)n;return gaokun;}
static void mutex_lock(int*m) {assert(!*m);*m=1;}
static void mutex_unlock(int*m) {assert(*m);*m=0;}
struct test_guard {int*m;};
static struct test_guard test_lock(int*m) {mutex_lock(m);return (struct test_guard){m};}
static void test_unlock(struct test_guard*g) {mutex_unlock(g->m);}
#define guard(name) struct test_guard _g __attribute__((cleanup(test_unlock))) = test_lock
static int clk_prepare_enable(void*c) {(void)c;enables++;if(clock_error)return -EIO;refs++;return 0;}
static void clk_disable_unprepare(void*c) {(void)c;assert(refs>0);refs--;disables++;}
static void event(void) {hardware++;if(guard_expected)assert(refs==1);}
static void qmp_combo_usb_power_off(void*p) {(void)p;event();}
static void qmp_combo_usb_power_on(void*p) {(void)p;event();}
static void qmp_combo_com_exit(struct qmp_combo*q,bool f) {(void)q;(void)f;event();}
static void qmp_combo_com_init(struct qmp_combo*q,bool f) {(void)q;(void)f;event();}
static void aux(struct qmp_combo*q) {(void)q;event();}
static void writel(int v,char*p) {(void)v;(void)p;event();}
#define dev_dbg(...) ((void)0)
static void *typec_switch_get_drvdata(struct typec_switch_dev*s) {return s->q;}
static void *typec_mux_get_drvdata(struct typec_mux_dev*s) {return s->q;}
"""
