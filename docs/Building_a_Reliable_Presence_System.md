# Building a Reliable Home Assistant Presence System

This guide explains how to prepare Home Assistant presence tracking before installing HALP! (HA Location & Presence analyzer).

HALP! is an analyzer. It does not create a Person, install a phone app, configure a router, obtain a Bluetooth identity key, or decide which trackers should be assigned to someone. HALP! works with the location information Home Assistant already has.

A strong setup usually combines several independent technologies:

* GPS for long-range location and zones
* BLE for fast local presence confirmation
* Router/WiFi tracking for network-connected presence

Some parts of this guide are optional. A Person can work with only one tracker. However, multiple independent sources usually give HALP! more useful evidence to compare.

---

# Quick Prerequisite Checklist

Before installing HALP!, try to have the following ready for each Person:

- [ ] A Home Assistant Person entity
- [ ] A phone or other tracked device associated with that Person
- [ ] A GPS `device_tracker`, usually from the Home Assistant Companion App
- [ ] A BLE `device_tracker`, optional but recommended
- [ ] A router/WiFi `device_tracker`, optional but recommended
- [ ] The phone's WiFi, Bluetooth, and location services left enabled
- [ ] Home Assistant Companion App location permissions configured correctly
- [ ] Battery optimization disabled for the Companion App where required
- [ ] A stable WiFi identity for the phone
- [ ] All desired trackers assigned to the Person
- [ ] Each tracker tested independently before HALP! is added

---

# 1. Understand the Home Assistant Presence Model

## Person entities do not track anything by themselves

A Home Assistant Person is a logical entity that combines one or more `device_tracker` entities.

Examples of trackers that may be attached to a Person include:

* A GPS tracker created by the Home Assistant Companion App
* A BLE presence tracker for the person's phone
* A router tracker that reports whether the phone is connected to the home network

The Person state is influenced by the trackers assigned to it. Home Assistant also uses tracker source behavior when several trackers disagree. Review the official Person documentation for the current rules:

https://www.home-assistant.io/integrations/person/

## Device trackers are the actual evidence

A `device_tracker` may report:

* `home`
* `not_home`
* A named zone
* `unknown`
* `unavailable`

Some trackers include latitude, longitude, GPS accuracy, source type, or other attributes.

The official device tracker overview is here:

https://www.home-assistant.io/integrations/device_tracker/

## Zones provide geographic meaning

GPS-capable trackers can place a Person inside Home or another defined zone.

Review and verify your Home zone before troubleshooting presence:

https://www.home-assistant.io/integrations/zone/

A Home zone that is too small may cause late arrivals or early departures. A zone that is too large may report Home while the person is still nearby.

---

# 2. Create or Review the Home Assistant Person

In Home Assistant:

1. Go to **Settings → People**.
2. Create the Person if one does not already exist.
3. Give the Person a clear name.
4. Do not assign random trackers just because they are available.
5. First configure and test the GPS, BLE, and router/WiFi sources described below.
6. Return to the Person and assign the trackers after each one is known to work.

For a typical fully configured phone, the Person may eventually have:

* One GPS tracker
* One BLE tracker
* One router/WiFi tracker

More than one tracker of the same type is possible, but start simply. Adding several weak trackers can create more confusion rather than more reliability.

---

# 3. Prepare the Person's Phone

For the most dependable results, the phone should normally keep these features enabled:

* Location services or GPS
* Bluetooth
* WiFi

Turning one of these off removes an entire evidence source.

## Why WiFi should stay on

Router tracking cannot detect a phone that has WiFi disabled.

The phone may also delay reconnecting after arrival because of sleep, roaming, or battery-saving behavior. A router tracker is therefore useful supporting evidence, but should not normally be the only presence source.

## Why Bluetooth should stay on

Private BLE Device, Bermuda, ESPresense, and related systems depend on Bluetooth advertisements.

When Bluetooth is disabled, BLE presence will stop. Some phones also reduce advertising under aggressive battery-saving modes.

## Why location services should stay on

The Companion App GPS tracker depends on location permissions and device location services.

Without current GPS data, Home Assistant may miss zone transitions or continue displaying an old location.

---

# 4. Install and Configure the Home Assistant Companion App

The Home Assistant Companion App is the most common GPS source for Android and iPhone.

Official getting-started documentation:

https://companion.home-assistant.io/docs/getting_started/

The app creates a `device_tracker` and can expose supporting sensors such as battery state, network status, SSID, BSSID, and connection type.

## Basic setup

On the person's phone:

1. Install the official Home Assistant Companion App.
2. Connect it to the correct Home Assistant server.
3. Give the device a clear, stable name.
4. Enable location sharing.
5. Allow notifications if the household uses Home Assistant mobile notifications.
6. Open the app after installation and confirm it can reach Home Assistant both on and away from home WiFi.
7. In Home Assistant, open the Mobile App integration and identify the phone's `device_tracker`.

## Permissions are not identical on every phone

Android vendor menus and iOS wording can change over time. Use the current Companion App documentation together with the phone's system settings.

Companion App location documentation:

https://companion.home-assistant.io/docs/core/location/

Companion App sensor documentation:

https://companion.home-assistant.io/docs/core/sensors/

---

# 5. Android Companion App Recommendations

For Android, the goal is to let the Companion App receive location updates in the background without being suspended.

The exact menu names vary by phone manufacturer.

## Required or strongly recommended permissions

Configure the Home Assistant app with:

* Location permission set to **Allow all the time**
* Precise location enabled
* Nearby devices permission enabled when requested
* Background activity allowed
* Notifications allowed
* Mobile data allowed
* Background data allowed
* Unrestricted battery use, or exclusion from battery optimization
* Permission to run when the screen is off

The official Companion App documentation states that Android background location requires the appropriate location and nearby-device permissions.

## Disable manufacturer-specific sleeping behavior

Some Android manufacturers add extra power-management systems beyond standard Android battery optimization.

Look for settings such as:

* Sleeping apps
* Deep sleeping apps
* Auto launch
* Background usage limits
* App battery management
* Adaptive battery
* Pause app activity if unused
* Remove permissions if app is unused

Home Assistant should not be placed in a sleeping or deep-sleeping list.

When the phone offers battery choices such as Optimized, Restricted, and Unrestricted, use the choice that allows reliable background activity.

## Enable the relevant Companion App sensors

In the Companion App:

1. Open **Settings → Companion App → Manage sensors**.
2. Review the Location Sensors section.
3. Enable the sensors required for your setup.
4. Review network-related sensors such as WiFi connection, SSID, BSSID, and connection type if you want them available in Home Assistant.
5. Wait for each enabled sensor to send at least one update.

Not every optional sensor is required by HALP!. The important tracker for GPS is the phone's `device_tracker`.

## Test Android GPS tracking

1. Open the phone's `device_tracker` in Home Assistant.
2. Confirm it contains a recent update.
3. Leave the Home zone.
4. Confirm the tracker changes to `not_home` or another zone.
5. Return home and confirm it changes back.
6. Review the Companion App's location troubleshooting page if updates are missing.

Troubleshooting documentation:

https://companion.home-assistant.io/docs/troubleshooting/faqs/

---

# 6. iPhone Companion App Recommendations

For iPhone, Home Assistant relies on the location behaviors allowed by iOS.

## Recommended iOS settings

For the Home Assistant app:

* Location set to **Always**
* Precise Location enabled
* Background App Refresh enabled
* Bluetooth allowed
* Local Network allowed where requested
* Notifications allowed if used
* Cellular data enabled
* Motion & Fitness allowed when requested by relevant app features

Keep WiFi, Bluetooth, and Location Services enabled on the phone.

## Important iOS behavior

iOS manages background execution itself. There is no exact equivalent to every Android battery menu.

Do not repeatedly force-close the Home Assistant app. Force-closing an iOS app can interfere with background behavior until the app is opened again.

Open Home Assistant periodically and after major phone or app updates to confirm it remains connected and authorized.

## Test iPhone GPS tracking

Use the same real-world test:

1. Confirm the phone's `device_tracker` updates.
2. Leave the Home zone.
3. Confirm the Person or tracker changes.
4. Return and confirm arrival.
5. Review Home Assistant and Companion App logs if updates are delayed.

---

# 7. GPS Tracking

GPS is usually the best source for:

* Long-range away status
* Arrival at Home
* Departure from Home
* Named zones such as Work or School

GPS is not perfect.

Possible problems include:

* Background permission removed
* Battery optimization
* Poor satellite reception
* Delayed mobile-data connection
* An oversized or undersized Home zone
* The app being force-closed
* The phone reporting an old location

## Find the GPS tracker

After the Companion App is configured:

1. Go to **Settings → Devices & services**.
2. Open the **Mobile App** integration.
3. Open the person's phone.
4. Find the `device_tracker` entity associated with that phone.
5. Verify that it contains meaningful location information.
6. Give it a clear friendly name if needed.

Do not confuse the GPS `device_tracker` with supporting sensors such as geocoded location, connection type, or SSID.

## Alternative GPS sources

HALP! can also analyze other GPS-capable `device_tracker` entities, such as trackers created by iCloud3 or another location integration.

Classify a tracker as GPS only when it represents geographic location evidence.

---

# 8. BLE Presence Tracking

BLE provides local evidence that a phone or device is near the home or within Bluetooth coverage.

BLE is valuable because it can confirm presence even when GPS is delayed.

Possible BLE approaches include:

* Home Assistant Private BLE Device
* Bermuda
* ESPresense
* Other integrations that create a suitable `device_tracker`

HALP! does not require a specific BLE integration. It only requires a working BLE `device_tracker`.

## Bluetooth coverage

BLE detection requires one or more Bluetooth receivers that can hear the phone.

Possible receivers include:

* A Bluetooth adapter connected to the Home Assistant host
* ESPHome Bluetooth proxies
* Supported devices capable of forwarding Bluetooth advertisements

One receiver may not cover an entire house. Walls, floors, metal, electrical equipment, and distance can reduce reception.

Place receivers where they provide useful coverage rather than assuming one centrally located receiver is enough.

---

# 9. Private BLE Device and Obtaining the IRK

Modern phones commonly use resolvable private Bluetooth addresses. Their visible Bluetooth address changes over time.

Home Assistant can recognize these devices when it knows the Identity Resolving Key, commonly called the IRK.

Official documentation:

https://www.home-assistant.io/integrations/private_ble_device/

## Follow the official instructions exactly

Obtaining the IRK can be the hardest part of BLE setup.

The official page provides several platform-specific methods. The section titled:

**On Windows - for any devices that will connect to a computer**

is especially useful for phones that can be paired to a Windows computer.

This procedure has worked for both Android and iOS devices when followed carefully, but the order matters.

Important precautions:

1. Read the complete Windows section before starting.
2. Follow every pairing and removal step in the documented order.
3. Do not skip a step because the phone already appears paired.
4. Use the correct phone entry when extracting the key.
5. Verify the complete IRK value before entering it into Home Assistant.
6. Keep Bluetooth enabled during testing.

Do not publish an IRK or include it in screenshots. Treat it as device-identifying information.

## Add Private BLE Device

After obtaining the IRK:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **Private BLE Device**.
4. Follow the integration flow.
5. Enter the requested device information and IRK.
6. Wait for Home Assistant or a Bluetooth proxy to receive advertisements.
7. Confirm the integration creates a device tracker or presence entity suitable for your setup.

## Test BLE separately

Before assigning it to a Person:

1. Confirm the BLE tracker reports Home while the phone is present.
2. Leave Bluetooth coverage with the phone.
3. Wait for the tracker's away behavior.
4. Return and confirm it detects the phone again.
5. Repeat from several locations in the home.

Do not assume a BLE tracker is reliable because it detected the phone once.

---

# 10. Router and WiFi Tracking

Router tracking reports whether the phone appears connected to the home network.

Examples include integrations for:

* UniFi
* Omada
* OpenWRT
* FRITZ!Box
* Other Home Assistant-supported network systems

Router tracking is local and does not require GPS, but it depends on the phone maintaining a recognizable network identity.

## Find the router tracker

1. Add and configure the supported router or controller integration.
2. Find the phone in the integration's device list.
3. Locate the resulting `device_tracker`.
4. Verify that it reports Home while the phone is connected.
5. Disconnect the phone from WiFi or leave the property.
6. Confirm the tracker eventually changes to away.

Router integrations differ in update frequency and how quickly they consider a disconnected client away.

## A DHCP reservation is strongly recommended

Configure the router or DHCP server so the phone receives a consistent local IP address.

This is often called:

* DHCP reservation
* Address reservation
* Static lease
* Fixed IP assignment

The reservation is configured on the router. It maps the phone's network hardware address to a chosen IP address.

However, a reservation alone is not enough when the phone changes the MAC address it presents to the network.

---

# 11. MAC Address Randomization

Modern Android and iPhone devices use private or randomized WiFi addresses to reduce tracking across networks.

This is good for privacy on public networks, but it can break router-based presence tracking when the identity changes for the home network.

## Why the IP address alone is not enough

The router normally assigns an IP address based on the client's MAC address.

A router cannot force a phone to keep using the same identity when the phone presents a different MAC address.

If the phone changes its MAC address:

* The DHCP reservation may no longer apply
* The router may create a new client record
* Home Assistant may track the old client while the phone uses the new one
* Presence may appear unreliable or stop working

## Configure a stable identity for the home network

On the phone, open the settings for the specific home WiFi network.

Choose the option that keeps the same address for that network.

Depending on the device, wording may include:

* Device MAC
* Phone MAC
* Use device MAC
* Fixed private address
* Private WiFi address
* Randomized MAC

Apple and Android implementations change over time. The goal is not necessarily to disable privacy everywhere. The goal is to ensure the phone uses a stable, repeatable identity on the trusted home SSID.

After changing this setting:

1. Forget and reconnect to the home network if required.
2. Check the MAC address currently presented to the router.
3. Update the router's DHCP reservation to match that address.
4. Remove or ignore obsolete duplicate client records.
5. Verify Home Assistant is tracking the active client entity.

## Do not assume static IP means static identity

A manually entered phone IP may create other networking problems and still does not solve changing MAC identity.

For most homes, use:

* Automatic DHCP on the phone
* A DHCP reservation on the router
* A stable MAC identity for the home SSID

---

# 12. Test Router Tracking Carefully

Router trackers may be slow to mark a sleeping phone away.

Test several conditions:

* Phone connected and actively used
* Phone screen off
* Phone charging
* Phone not charging
* Phone roaming between access points
* Phone leaving and returning
* WiFi toggled off and back on
* Phone restarted

A reliable router tracker should reconnect consistently and should not create new client identities after routine reconnects.

HALP! can show when router evidence disagrees, but it cannot fix router firmware, client roaming, DHCP, or phone power management.

---

# 13. Assign Trackers to the Person

After testing each tracker independently:

1. Go to **Settings → People**.
2. Open the Person.
3. Find the device-tracker assignment area.
4. Assign the person's GPS tracker.
5. Assign the person's BLE tracker, when used.
6. Assign the person's router/WiFi tracker, when used.
7. Save the Person.

Use only trackers that actually belong to that Person.

Do not assign:

* A shared tablet unless its location truly represents that Person
* A work phone the Person routinely leaves behind
* An old phone that is no longer carried
* A vehicle tracker unless vehicle location intentionally represents the Person
* A tracker that frequently changes identity

HALP! can classify an assigned tracker as Ignore, but Home Assistant will still use every tracker assigned to the Person. Remove a tracker from the Person when Home Assistant itself should not use it.

---

# 14. Understand Multiple Trackers on a Person

Home Assistant combines assigned trackers according to its Person logic.

Read the current official rules:

https://www.home-assistant.io/integrations/person/

This matters because GPS and non-GPS trackers are not always treated identically.

HALP! does not replace these rules. HALP! separately analyzes the configured trackers and creates its own Vetted Location result.

When HALP! Ignore is used:

* HALP! excludes that tracker
* Home Assistant Person does not exclude it
* The default Person state may therefore differ from HALP! Vetted Location

For automations where the ignored tracker must not influence the decision, use HALP!'s Vetted Location sensor rather than relying only on the default Person entity.

---

# 15. Verify the Complete Person Before Installing HALP!

Do not judge the setup from a single moment.

Perform real-world tests over several days.

## Departure test

1. Begin at Home with all relevant phone radios enabled.
2. Confirm GPS, BLE, router, and Person report Home.
3. Leave the property.
4. Record when each source changes.
5. Confirm the Person eventually reports away.
6. Note any tracker that remains Home incorrectly.

## Arrival test

1. Confirm the Person and trackers report away.
2. Return home normally.
3. Record when GPS enters the Home zone.
4. Record when BLE detects the phone.
5. Record when WiFi reconnects.
6. Confirm the Person changes to Home.

## Overnight test

Phones often behave differently while idle.

Confirm:

* Router presence remains stable
* BLE still receives advertisements
* GPS does not become unavailable unnecessarily
* The phone is not placed into deep sleep by the operating system

## Reboot test

Restart the phone and confirm all three tracker types recover.

Restart Home Assistant and confirm all entities return.

---

# 16. Common Problems

## GPS stays Home after departure

Check:

* Location permission
* Precise location
* Battery optimization
* Mobile data
* Whether the Companion App was force-closed
* Home zone size
* Last-updated time

## GPS stays away after arrival

Check:

* Background location permission
* Phone data connection
* Companion App connectivity
* Home zone placement
* Whether the app can reach Home Assistant remotely

## BLE never detects the phone

Check:

* Bluetooth is enabled
* IRK is correct
* The Private BLE Device procedure was followed exactly
* Bluetooth receivers or proxies are online
* The phone is within coverage
* The receiver can hear other BLE devices

## BLE is intermittent

Check:

* Receiver placement
* Number of Bluetooth proxies
* Floor and wall coverage
* Phone battery-saving behavior
* Bluetooth radio state

## Router tracker creates duplicate phones

Check:

* MAC randomization
* Private WiFi address behavior
* Whether the phone changed its network identity
* DHCP reservations
* Old client records in the router
* Which entity Home Assistant is tracking

## Router tracker remains Home too long

Check:

* Router integration polling interval
* Controller disconnect timeout
* Phone sleep behavior
* Whether another access point still reports the client
* Whether the integration uses last-seen data

## Person state seems wrong

Open every assigned `device_tracker` and compare its state.

Remove obsolete trackers.

Read the Person integration rules.

HALP! becomes useful here because it exposes agreement, freshness, conflicts, and its own Vetted Location.

---

# 17. Recommended Typical Configuration

For each regularly tracked Person:

## GPS

* Home Assistant Companion App installed
* Always/background location permission
* Precise location enabled
* Battery optimization excluded
* Phone's GPS/location services enabled

## BLE

* Phone Bluetooth enabled
* Private BLE Device or another BLE presence system
* Correct IRK when required
* Enough Bluetooth receivers to cover the intended area

## Router/WiFi

* Supported router or controller integration
* Stable MAC identity for the home SSID
* DHCP reservation on the router
* Phone WiFi enabled
* Correct active client entity selected

## Person

* GPS tracker assigned
* BLE tracker assigned
* Router tracker assigned
* No obsolete or unrelated trackers assigned

## HALP!

* GPS tracker classified as GPS
* BLE tracker classified as BLE
* Router tracker classified as WiFi
* Only deliberate exclusions classified as Ignore
* Weights left at defaults until enough evidence has been observed

---

# 18. Optional Components

Not every household needs every component.

## GPS-only setup

Works for zone-based tracking, but HALP! has no local BLE or router evidence to compare.

## GPS plus router

Provides long-range location plus network presence.

## GPS plus BLE

Provides long-range location plus fast local confirmation.

## BLE plus router without GPS

May work for Home and Away presence, but does not provide meaningful geographic zone tracking away from home.

## Multiple trackers of one type

HALP! supports multiple GPS, BLE, or router trackers. Add them only when each source provides distinct and useful evidence.

---

# 19. Privacy and Security

Location and presence data are sensitive.

Recommended practices:

* Give Home Assistant access only to the data required
* Secure remote access
* Use strong authentication
* Protect backups
* Do not publish entity dumps containing personal names or coordinates
* Do not publish IRKs
* Avoid screenshots that expose home addresses, SSIDs, IP addresses, or unique device identifiers
* Keep Home Assistant, HACS, integrations, and phone apps updated

HALP! runs locally in Home Assistant and does not use AI during installation or operation.

---

# 20. Ready for HALP!

You are ready to install HALP! when:

- The Person exists
- At least one assigned tracker works
- The phone permissions are correct
- The Home zone is correct
- BLE works when configured
- Router tracking uses a stable client identity when configured
- Assigned trackers belong to the correct Person
- Obsolete trackers have been removed

Return to the HALP! README and follow the Installation section.

After HALP! is configured, use its entities to evaluate:

* Vetted Location
* Location Confidence
* Consensus Score
* Source Health
* Conflict Details
* Stale Sources
* Location Explanation
* Historical trends

HALP! will not make the phone or router report more accurately, but it will make their behavior much easier to understand.
