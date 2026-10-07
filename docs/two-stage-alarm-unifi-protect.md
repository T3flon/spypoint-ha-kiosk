# Two-stage alarm with UniFi Protect person detection

This is a companion idea from the same Home Assistant setup as the SpyPoint
kiosk: an indoor UniFi Protect camera whose built-in AI person detection
decides whether an alarm gets *loud*. It is not tied to SpyPoint at all —
use it with any alarm panel and contact sensors.

All entity IDs below are placeholders (`YOUR_…`). Adapt them to your setup.

## The idea

A plain contact sensor is a weak alarm trigger on its own: a flaky sensor,
dust in an optical contact, or a window you forgot open will wake you up
for nothing. A camera that actually sees a person is a much stronger signal.
So the alarm is split into two stages:

| Stage | Trigger (while armed away) | Reaction |
|---|---|---|
| 1 — pre-warning | a door/window contact changes | quiet push every 5 min until you tap "Seen" |
| 2 — loud alarm | the camera's AI detects a **person** | loud, sticky push with a camera snapshot (+ lights, escalation, …) |
| fallback | stage 1 fires while the camera is **blind** | escalates straight to stage 2 |

The fallback matters: if the camera is offline, in privacy mode or not
recording, a contact must still be able to raise the loud alarm — otherwise
the camera becomes a single point of failure.

## Requirements

- UniFi Protect camera with Smart Detections, integrated via the official
  `unifiprotect` integration (exposes `binary_sensor.<camera>_person_detected`).
- **Storage in the Protect console.** Without a disk, Motion/AI events stay
  disabled and the person sensor simply never turns on — no error anywhere.
- Recording mode `always` (or `detections`) on the camera.
- An `alarm_control_panel`, contact sensors, and the HA Companion App.
- A presence sensor based on your home Wi-Fi (recommended, see stage 2).

## Stage 1: contact → quiet pre-warning

```yaml
- id: alarm_stage_1_contact
  alias: "Alarm stage 1: contact changed (quiet pre-warning)"
  mode: queued
  max: 10
  triggers:
    - trigger: state
      entity_id:
        - binary_sensor.YOUR_FRONT_DOOR
        - binary_sensor.YOUR_WINDOW
      from: "off"            # explicit from/to: attribute-only updates
      to: "on"               # (RSSI, battery) must not trigger
  conditions:
    - condition: state
      entity_id: alarm_control_panel.YOUR_PANEL
      state: armed_away
  actions:
    # Camera blind? Then a contact is all we have -> escalate to stage 2.
    - if:
        - condition: template
          value_template: >
            {{ states('binary_sensor.YOUR_CAMERA_person_detected') in ['unavailable', 'unknown']
               or is_state('switch.YOUR_CAMERA_privacy_mode', 'on')
               or is_state('select.YOUR_CAMERA_recording_mode', 'never') }}
      then:
        - event: alarm_fallback
          event_data:
            source: "{{ trigger.to_state.name }}"
        - stop: "Camera blind - escalated to stage 2"
    - repeat:
        sequence:
          - action: notify.mobile_app_YOUR_PHONE
            continue_on_error: true
            data:
              title: "Contact while armed"
              message: "{{ trigger.to_state.name }} changed. No person detected (yet)."
              data:
                tag: alarm_prewarning
                channel: Alarm pre-warning
                actions:
                  - action: ALARM_PREWARNING_OK
                    title: Seen
          - wait_for_trigger:
              - trigger: event
                event_type: mobile_app_notification_action
                event_data:
                  action: ALARM_PREWARNING_OK
            timeout: "00:05:00"
            continue_on_timeout: true
        until:
          - condition: template
            value_template: >
              {{ wait.trigger is not none
                 or not is_state('alarm_control_panel.YOUR_PANEL', 'armed_away')
                 or repeat.index >= 96 }}
```

## Stage 2: person detected → loud alarm

```yaml
- id: alarm_stage_2_person
  alias: "Alarm stage 2: person detected (loud alarm)"
  mode: single
  triggers:
    - trigger: state
      entity_id: binary_sensor.YOUR_CAMERA_person_detected
      from: "off"
      to: "on"
      id: person
    - trigger: event
      event_type: alarm_fallback
      id: fallback
  conditions:
    - condition: state
      entity_id: alarm_control_panel.YOUR_PANEL
      state: armed_away
    # Coming home: your phone joins the home Wi-Fi before you open the door.
    # This keeps the camera from screaming at you in the race before the
    # panel is disarmed.
    - condition: state
      entity_id: binary_sensor.YOUR_HOME_WIFI_PRESENCE
      state: "off"
  actions:
    - action: notify.mobile_app_YOUR_PHONE
      continue_on_error: true
      data:
        title: "🚨 INTRUSION ALARM"
        message: >
          {% if trigger.id == 'person' %}Person detected by the camera.
          {% else %}Camera unavailable - contact "{{ trigger.event.data.source }}" changed.{% endif %}
        data:
          tag: intrusion_alarm
          channel: Intrusion alarm
          importance: high
          sticky: true
          image: /api/camera_proxy/camera.YOUR_CAMERA
          actions:
            - action: ALARM_ACK
              title: Stop alarm
    # add your loud parts here: lights, repeated pushes, TTS, e-mail escalation ...
```

Note for Android: a notification channel's sound and vibration pattern are
fixed the first time the channel is created. To change them later, use a new
channel name.

## Watchdog: camera blind while armed

The fallback covers the alarm itself, but you also want to *know* when the
camera can't see. A periodic check survives restarts, unlike a `for:` on a
trigger:

```yaml
- id: camera_blind_while_armed
  alias: "Camera blind while armed"
  mode: single
  triggers:
    - trigger: time_pattern
      minutes: "/5"
  conditions:
    - condition: state
      entity_id: alarm_control_panel.YOUR_PANEL
      state: armed_away
    - condition: template
      value_template: >
        {{ states('binary_sensor.YOUR_CAMERA_person_detected') in ['unavailable', 'unknown']
           or is_state('switch.YOUR_CAMERA_privacy_mode', 'on')
           or is_state('select.YOUR_CAMERA_recording_mode', 'never') }}
  actions:
    - action: notify.mobile_app_YOUR_PHONE
      data:
        title: "Camera blind while armed"
        message: "Person detection is not working - contacts trigger the loud alarm directly."
        data:
          tag: camera_blind
```

Add an `input_boolean` as a flag if you only want one warning plus an
all-clear instead of a push every 5 minutes.

## Self-healing after a restart without network

If Home Assistant boots while the network is still down (power cut,
gateway reboot), integrations like UniFi Protect can end up in
`setup_error`. Unlike `setup_retry`, Home Assistant does **not** retry
that state on its own — the camera stays unavailable until someone reloads
it. A small periodic job fixes that:

```yaml
- id: self_heal_camera
  alias: "Self-heal: reload stuck camera integration"
  mode: single
  triggers:
    - trigger: time_pattern
      minutes: "/5"
  actions:
    - if:
        - condition: state
          entity_id: camera.YOUR_CAMERA
          state: unavailable
          for: "00:05:00"
      then:
        - action: homeassistant.reload_config_entry
          continue_on_error: true
          target:
            entity_id: camera.YOUR_CAMERA   # works in setup_error, the entity stays in the registry
    - if:
        - condition: state
          entity_id: switch.YOUR_CAMERA_privacy_mode
          state: "off"
          for: "00:05:00"
        - condition: state
          entity_id: select.YOUR_CAMERA_recording_mode
          state: never
          for: "00:05:00"
      then:
        - action: select.select_option
          continue_on_error: true
          target:
            entity_id: select.YOUR_CAMERA_recording_mode
          data:
            option: always
```

The same pattern works for your alarm panel's integration.

## Pitfalls we hit

- **No storage, no AI.** Without a disk in the Protect console the
  detection switches stay unavailable and the person sensor never fires.
- **Privacy mode overwrites the recording mode.** When HA turns privacy
  mode on, it remembers the current recording mode and restores it when
  privacy goes off. But that memory only lives until the next HA restart.
  After a restart, privacy-off can restore `never` — the camera streams, but
  records and detects nothing. Re-check the recording mode after turning
  privacy off (see the self-heal job above).
- **`for:` on triggers resets** on every HA restart and on every
  `unavailable` blip. For anything safety-related, prefer a periodic
  `time_pattern` check of the current state.
- **`setup_error` is not retried** automatically (see self-healing).
- **Use explicit `from`/`to`** on contact triggers. A bare state trigger also
  fires on attribute updates (signal strength, battery).
- **Pets.** Protect separates "person" from "animal". In our test a cat
  was reported as an animal only and never as a person — still, test with
  your own pets before you trust it.

## Status

Person detection and the watchdog/self-healing jobs are in daily use.
Test the full chain in your own home before you rely on it: arm away,
open a contact, walk past the camera.
