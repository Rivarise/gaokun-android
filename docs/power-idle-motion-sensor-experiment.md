# Let deep Doze progress without an unavailable wake-up motion sensor

The gaokun3 sensor HAL exposes accelerometer and gyroscope readings, but the
tested device has no wake-up significant-motion/motion-detect sensor selected
by DeviceIdleController. The running service reports
`mUseMotionSensor=true mMotionSensor=null`. This prevents normal deep Doze
progression despite long, unplugged, screen-off periods.

## Change

Set `config_autoPowerModeUseMotionSensor=false` in the existing device framework
resource overlay. This uses Android's existing sensor-independent idle path.
Accelerometer/gyroscope and screen rotation remain available. No kernel,
firmware, NTP setting, app whitelist, alarm timer, force-idle command or sensor
HAL is changed by this PR.

The production change is a build-time resource overlay. The local KSU module
used to validate it is not a runtime dependency and is not shipped in this PR.

## Android 17 source

[DeviceIdleController.java, android-17.0.0_r1](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-17.0.0_r1/apex/jobscheduler/service/java/com/android/server/DeviceIdleController.java)
reads this bool in `Injector.useMotionSensor()` (lines 2612-2614).
`scheduleAlarmLocked()` (lines 4363-4376) returns without scheduling normal
idle alarms when motion sensing is required but no motion sensor is selected.
The quick-idle and already-idle cases have their own exceptions. This change
addresses normal automatic progression, without pretending a sensor exists.

## Real-device evidence

Device: MateBook E Go gaokun3. Android 16 RC2 and Android 17 build
`20261030010048` were observed separately.

* Android 16: before the change, light idle appeared but deep idle did not.
  After a single-resource early immutable overlay and reboot, both system
  resource views and the running service reported false. In an unplugged,
  stationary test on 2026-10-29, screen off was at 15:58:05.977, natural
  `device_idle=full` at 16:00:30.807 and manual wake at 16:04:47.122.
  No force-idle command was used; USB audio after wake was confirmed working.
* With that configuration still active, the following longer observation lost
  42 percentage points in approximately ten screen-off hours. Deep Doze alone
  therefore did not fix total platform standby power.
* After updating to Android 17, the RC2-specific local module rejected SDK37
  and disabled itself. The service again reported true with a null sensor.
  On 2026-10-31, 01:08:14 to 09:11:04, battery fell from 83% to 22%.
  That window recorded light idle but no full idle. This is not a controlled
  battery A/B comparison with Android 16.
* The same resource APK was verified on A17 inside an isolated private mount
  namespace: `Resources.getSystem` and a fresh system context both read false,
  existing system overlays remained loaded, and the parent namespace retained
  its original resources. The resource ID changed between releases, so the
  probe resolved it by name.
* An A17-build-pinned early module was then enabled and the user approved a
  reboot. On the new boot the module reported `EARLY_IMMUTABLE_BIND_APPLIED`,
  the actual DeviceIdleController reported `mUseMotionSensor=false`, and the
  kernel and accepted stylus executable hashes matched the pre-reboot values.
  A17 natural idle/wake was then confirmed: unplugged at 10:18:00.278,
  screen off at 10:18:08.972, unforced `device_idle=full` at 10:20:40.639,
  manual wake at 10:20:52.772 and USB reconnect at 10:21:14.258. The user
  reported normal wake. Deep idle was observed for only about twelve seconds
  before manual wake, so this is entry/wake acceptance, not prolonged residency
  or battery-life validation. Across the before/after snapshots (including
  brief connected periods), suspend success increased 0 to 7 and failures
  0 to 2; AOSD/CXSD remained zero.

Private raw logs, application/network identifiers, signing materials and local
module mechanics are intentionally outside the repository.

## Limits and relation to other power work

Android deep Doze restricts background work and network policy. Kernel s2idle,
Qualcomm CX/DDR collapse and actual energy discharge are separate outcomes.
This PR complements the Wi-Fi/ADSP/PM work in #44, #46 and #48; it does not
replace their fixes or claim their results. The observed firmware crashes and
zero CX/AOSD counters remain separate problems. Sensor-independent Doze also
does not provide motion-based detection for a device being carried.

## Verify a ROM built with this overlay

1. Reboot and confirm the framework resource and actual running service both
   report false; confirm `mForceIdle=false`.
2. Save boot ID, battery history, suspend success/fail and QCOM residency stats.
3. Unplug both USB ports, turn the screen off and leave the tablet stationary.
   Wake manually and reconnect. Confirm natural `device_idle=full` in history
   and compare only counters from the same boot. Entry time depends on current
   idle timers, alarms and other constraints; do not change timers to prove it.
4. Check input/USB audio after waking, then do a separate overnight battery run.

Reverting the bool to the framework default and rebuilding restores the prior
sensor-dependent behavior. Resource changes require a fresh service startup;
a lookup that changes while the existing service still reports true is not
successful validation.
