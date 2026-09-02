-- WirePlumber 0.4.8 (Ubuntu 22.04). Both bcm2835 ALSA cards (HDMI, Headphones) get identical
-- node/device names from WirePlumber, so match on api.alsa.card.name instead.
--
-- NOTE: do NOT use ["node.disabled"] = true here. On 0.4.8 it leaves the session manager
-- unable to route any stream ("no node available"). Disabling at the *device* level works.

-- HDMI audio is never used (the speaker is on the 3.5 mm jack). Disable the whole card.
-- "bcm2835 HDMI 1" = firmware audio driver; "vc4-hdmi*" = name once vc4-kms-v3d is active.
table.insert(alsa_monitor.rules, {
  matches = {
    { { "device.name", "matches", "alsa_card.*" }, { "api.alsa.card.name", "matches", "*HDMI*" } },
    { { "device.name", "matches", "alsa_card.*" }, { "api.alsa.card.name", "matches", "vc4-hdmi*" } },
  },
  apply_properties = {
    ["device.disabled"] = true,
  },
})

-- 3.5 mm jack = the room speaker: stable name, friendly description, preferred sink.
table.insert(alsa_monitor.rules, {
  matches = {
    {
      { "api.alsa.card.name", "equals", "bcm2835 Headphones" },
      { "media.class", "equals", "Audio/Sink" },
    },
  },
  apply_properties = {
    ["node.name"] = "alsa_output.room_speaker",
    ["node.description"] = "Room speaker (3.5 mm)",
    ["node.nick"] = "Room speaker",
    ["priority.session"] = 2000,
    ["priority.driver"] = 2000,
  },
})
