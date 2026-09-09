-- Headless Pi: WirePlumber 0.4.8 gates the Bluetooth monitor on an *active* logind
-- session (scripts/monitors/bluez.lua lines 152-171). With Linger=yes and no login the
-- user state is "lingering", so the A2DP sink endpoint only exists while someone is SSHed
-- in and a phone cannot connect otherwise. Redefine enable() without the logind module
-- (30-bluez-monitor.lua defines it; 90-enable-all.lua calls it; fragments run in name order).
function bluez_monitor.enable()
  load_monitor("bluez", {
    properties = bluez_monitor.properties,
    rules = bluez_monitor.rules,
  })
end
