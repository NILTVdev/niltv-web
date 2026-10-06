# Streaming tab prototype (esports)

A dev-only mockup of a Streaming tab: live Twitch and YouTube Live embeds, a
schedule and a past-streams rail. The page is `/streaming/`; the tab shows in
the nav of that page only.

## Where it lives and how it stays off prod

| Piece | File |
|---|---|
| Page content (hero, CSS, markup, script) | `scripts/builders/streaming_page.py` |
| Page build | `build-sections.py` (`page("streaming", ...)`, with `extra_css` / `extra_tab`) |
| Promotion + SEO | `promote.py` |
| Generated page | `streaming/index.html` |

Prod gate: `streaming/` is not in the `$pages` whitelist in `deploy.ps1`, so
the prod stage never copies it. Only the dev artifact adds it, next to
`vote`, `athletes` and `partners`. The dev sitemap lists it and the prod one
does not. The shared chrome (`cinema-template.html`) is unchanged, so no other
page links to it.

Everything on the page is mock data except the players. Schools and teams
are made up, and schedule times are generated relative to the current time
so the page always looks current. "Remind me" toggles in place and is not
wired to anything.

## Embed findings

**Twitch** (`player.twitch.tv`)

- Needs a `parent` parameter naming the embedding host. The page reads it
  from `location.hostname`, so localhost, the dev site and niltv.com all work
  without a rebuild. Twitch refuses to play under a host that is not listed.
- Twitch documents a 400 x 300 minimum player size, and autoplay depends on
  meeting it. A full-width 16:9 player on a phone is about 350-370px wide,
  under the minimum. The embed still renders, but autoplay is not
  guaranteed and viewers tap play. The page shows the live player size and
  a warning under the player so testers can see this.
- On mobile the player waits for a tap before playing, whatever the size.
- Live: `?channel=<login>`. Past broadcast: `?video=v<id>`.
  Collection: `?collection=<id>`.

**YouTube** (`youtube.com/embed`)

- Embedding a live stream **by its video ID** works on desktop and phone,
  and autoplays muted.
- The channel-based URL (`/embed/live_stream?channel=<UC id>`) showed "This
  video is unavailable" in testing, on a channel that was live at the time.
  This URL form is not in YouTube's player documentation, so we should not
  build on it. Use the video ID of each live stream.
- Minimum player size is 200 x 200. The player now has a 220px minimum
  height, so a 16:9 player on a 390px phone (about 195px tall) still meets
  it.
- Past streams: `/embed/<video id>`, or a playlist with
  `/embed/videoseries?list=<id>`. A channel's uploads playlist is its channel
  ID with `UC` changed to `UU`; the mock replays use this.
- Use `playsinline=1` so iOS plays in the page, not fullscreen.

## Test results

Run against the local server (`scripts/dev/serve.py`) in headless Chrome,
with device emulation (viewport, pixel ratio, touch, user agent).

| Check | iPhone (390 x 844) | Android (412 x 915) | Desktop (1440 x 900) |
|---|---|---|---|
| Twitch live embed loads, `parent` accepted | yes | yes | yes |
| YouTube Live by video ID plays | yes | yes | yes |
| YouTube replay (uploads playlist) loads | yes | yes | yes |
| No horizontal overflow | yes | yes | yes |
| Meets Twitch 400 x 300 | no (349 x 218) | no (369 x 218) | yes (896 x 503) |
| Meets YouTube 200 x 200 | yes | yes | yes |

Not covered yet, to do on the dev site after deploy:

- Real phones: iOS Safari and Android Chrome on hardware, including
  fullscreen and rotation. Emulation does not reproduce mobile autoplay
  rules exactly.
- Twitch with a channel that is actually live. The test channel was offline
  during testing: the offline card rendered, which shows the embed and
  `parent` work, but not live playback. Use "Test any channel" with any live
  channel.
- The dev site over HTTPS, under its own hostname as the Twitch `parent`.
- Phones on the local server through a LAN IP: Twitch may refuse non-HTTPS
  hosts other than localhost, so test phones on the dev URL.

## What an esports partner would need to provide

**Channels**

- Twitch: the channel login name(s) the matches stream on.
- YouTube: the channel ID (`UC...`), plus **the video ID or watch URL of each
  live stream**. Scheduling streams in YouTube Studio creates the watch URL
  ahead of time, so it can come with the schedule.
- YouTube settings on each stream: public or unlisted (private streams
  cannot be embedded), "Allow embedding" on, and not age-restricted
  (age-restricted videos do not play in embeds).
- Twitch: mature-content settings on the channel, which may put a warning in
  front of the embed.

**Schedule**, per match, in a feed we can read (shared sheet, calendar feed
or JSON/API):

- Start time with time zone, and expected length
- Teams / schools and the game
- Event or league name, round or week
- Platform and channel, plus the YouTube video ID once it exists
- Changes and cancellations through the same feed, so the page never shows a
  stale match

**Past streams**

- Twitch: VOD IDs, or a collection, for the broadcasts to feature. Past
  broadcasts on Twitch expire after a retention window unless they are
  saved as highlights or uploads, so the partner should keep the ones we
  link to.
- YouTube: video IDs or a playlist ID of finished streams.
- Titles, dates and a thumbnail per stream, or permission to use the
  platform's own thumbnails.

**Rights and contacts**

- Written permission to embed the streams and present them under NIL TV.
- Team and school names and logos, with permission to show them. Logos go
  through the media pipeline, not this repo.
- Any sponsor exclusivity on the broadcast that could conflict with NIL TV
  brand partners.
- Player ages: confirm no minors appear, or provide guardian consent.
- Copyrighted music in streams: Twitch mutes it in VODs and YouTube can
  block it, so replays may differ from the live broadcast.
- A contact reachable during live events for outages or wrong streams.

## Before this could go to prod

- Load streams, the schedule and replays from the content API instead of
  constants in the page script.
- Show "Live now" from real live status: Twitch's API (needs a NIL TV app
  registration and a server-side call) or the partner's schedule feed.
  YouTube's search API has a small daily quota, so polling it per page view
  is not an option.
- Wire "Remind me" to an account feature or a calendar file.
- Add the Streaming tab to the shared chrome and the prod page whitelist.
- Review the privacy policy: Twitch and YouTube embeds set third-party
  cookies. YouTube's privacy-enhanced host (`youtube-nocookie.com`) is an
  option to test.
