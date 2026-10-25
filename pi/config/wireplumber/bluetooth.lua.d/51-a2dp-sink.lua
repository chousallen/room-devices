-- Pi acts as a Bluetooth speaker (A2DP sink) for the phone/laptop and as an A2DP source for
-- Bluetooth headphones (JLab). No headset/handsfree roles, so a phone cannot grab the
-- low-quality HFP profile.
bluez_monitor.properties["bluez5.roles"] = "[ a2dp_sink a2dp_source ]"
bluez_monitor.properties["bluez5.headset-roles"] = "[ ]"
bluez_monitor.properties["bluez5.enable-sbc-xq"] = true
bluez_monitor.properties["bluez5.enable-msbc"] = false
bluez_monitor.properties["bluez5.enable-hw-volume"] = true
