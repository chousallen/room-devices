-- Pi acts only as a Bluetooth speaker (A2DP sink). No headset/handsfree roles, so a phone
-- cannot grab the low-quality HFP profile.
bluez_monitor.properties["bluez5.roles"] = "[ a2dp_sink ]"
bluez_monitor.properties["bluez5.headset-roles"] = "[ ]"
bluez_monitor.properties["bluez5.enable-sbc-xq"] = true
bluez_monitor.properties["bluez5.enable-msbc"] = false
bluez_monitor.properties["bluez5.enable-hw-volume"] = true
