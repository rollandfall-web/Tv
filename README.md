# TV Ad Blocker and Speed-Up Kit

Removes home-screen ads and viewing trackers from your smart TV, and makes it run faster.

Most smart TVs slow down because of three things:

1. Ads and autoplaying previews on the home screen.
2. Viewing trackers (called ACR) that watch what is on screen and report it back.
3. Full storage and too many background apps.

This kit fixes all three. Start with **Step 1**, since it takes 5 minutes and needs no extra equipment.

> **What this cannot do:** No tool can remove ads *inside* YouTube, Hulu, Peacock and other streaming apps on a TV. Those ads come from the same servers as the shows, so blocking them stops the video too. For those, the only fix is the app's ad-free plan.

---

## Step 1: Turn off ads and tracking in the TV's settings (5 minutes, any TV)

Find your TV brand below and switch these **off**. Menu names change slightly between models.

| TV brand | Turn these off |
|---|---|
| **Samsung** | Settings > Support > Terms & Privacy > **Viewing Information Services** and **Interest-Based Advertisement**. Settings > General > **Autorun Smart Hub**. |
| **LG** | Settings > General > System > Additional Settings > **Home Promotion**, **Content Recommendation**. Settings > Support > **Live Plus**. User Agreements > untick **Viewing Information** and **Interest-Based Advertising**. |
| **Roku / Roku TV** | Settings > Privacy > Smart TV Experience > **Use Info from TV Inputs**. Settings > Privacy > Advertising > tick **Limit ad tracking**. |
| **Vizio** | Settings > Admin & Privacy > **Viewing Data**. |
| **Google TV** (Sony, TCL, Hisense, Chromecast) | Settings > Accounts & Sign In > your account > turn **on Apps only mode**. This removes the ad-filled recommendation rows and makes the home screen much faster. |
| **Amazon Fire TV** | Settings > Preferences > Featured Content > **Allow Video Autoplay** and **Allow Audio Autoplay**. Settings > Preferences > Privacy Settings > **Interest-based Ads**, **Collect App Usage Data**. |

Then, on any TV:

- Uninstall apps you don't use.
- Unplug the TV from the wall for 60 seconds. This clears its memory and often fixes slowness by itself.

---

## Step 2: Block ads for the whole house (30 minutes, needs an always-on computer)

This runs a small ad blocker called **AdGuard Home**. Your TV asks it before loading anything, and it refuses ad and tracker addresses. It works on every brand of TV, and on phones and computers too.

You need a computer that stays on, such as a Raspberry Pi, an old laptop, or a NAS, with [Docker](https://docs.docker.com/get-docker/) installed.

1. Copy this folder to that computer, then run:
   ```bash
   cd adguard
   docker compose up -d
   ```
2. Open `http://<that-computer's-IP>:3000` in a browser and follow the setup. When it asks for the web interface port, enter **80**. Afterwards, the dashboard is at `http://<that-computer's-IP>:8080`.
3. In the dashboard, go to **Filters > DNS blocklists > Add blocklist > Add a custom list**. Add the `blocklist.txt` file from this folder (paste its raw GitHub link, or copy its lines into **Filters > Custom filtering rules**).
4. Point your TV at the blocker. Pick **one**:
   - **Just the TV:** TV Settings > Network > IP / DNS settings > set DNS to **Manual** and enter the computer's IP address.
   - **Whole house:** in your Wi-Fi router's settings, set the DNS server to the computer's IP address.

**Already have Pi-hole?** Add `blocklist.txt` as an adlist instead. Pi-hole version 6 or newer reads this format.

**No spare computer?** Use [NextDNS](https://nextdns.io) (free tier). Add each domain from `blocklist.txt` to its Denylist, then put the DNS address it gives you into your TV.

**If something breaks** (an app won't load), open the AdGuard dashboard, go to **Query log**, find the blocked address, and click **Unblock**.

---

## Step 3: Extra speed-up for Android TV, Google TV, and Fire TV (optional)

`scripts/android-tv-speedup.sh` connects to your TV over Wi-Fi and:

- Shortens menu animations so the TV feels snappier.
- Turns off recommendation and ad services.
- Clears app caches.
- Lists the apps you installed, so you can remove ones you don't need.

Everything it changes can be undone. It deletes nothing.

### Turn on network debugging on the TV

- **Google TV:** Settings > System > About > click **Android TV OS build** 7 times. Then Settings > System > Developer options > turn on **USB debugging** (and **Network debugging** if listed).
- **Android TV (older models, e.g. Hisense):** Settings > Device Preferences > About > click **Build** 7 times. Then Settings > Device Preferences > Developer options > turn on **USB debugging**.

> **No computer?** You can set the animation speeds yourself in Developer options: set **Window animation scale**, **Transition animation scale**, and **Animator duration scale** to **0.5x**.
- **Fire TV:** Settings > My Fire TV > About > click **your device name** 7 times. Then Settings > My Fire TV > Developer Options > turn on **ADB Debugging**.

Find the TV's IP address under Settings > Network.

### Run it

**Windows:**

1. Download [Android platform-tools for Windows](https://developer.android.com/tools/releases/platform-tools) and unzip it into the `scripts` folder.
2. Right-click `scripts/android-tv-speedup.ps1` and choose **Run with PowerShell**.
3. Type your TV's IP address, then type **1** to speed it up (or **2** to undo).

**Mac / Linux:** on a computer on the same Wi-Fi, install [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (it includes `adb`), then:

```bash
./scripts/android-tv-speedup.sh 192.168.1.50          # use your TV's IP
```

A prompt appears on the TV the first time. Choose **Allow**.

To undo everything:

```bash
./scripts/android-tv-speedup.sh 192.168.1.50 --undo
```

When you are done, turn **USB/ADB debugging** back off on the TV.

---

## Files

| File | What it is |
|---|---|
| `blocklist.txt` | List of ad and tracker addresses for Samsung, LG, Roku, Vizio, Fire TV and Google TV. |
| `adguard/docker-compose.yml` | Starts the AdGuard Home ad blocker. |
| `scripts/android-tv-speedup.sh` | Speed-up script for Android TV, Google TV, and Fire TV. |
