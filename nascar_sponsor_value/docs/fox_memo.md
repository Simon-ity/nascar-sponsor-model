# Memo: packaging sponsor value for the whole field

**To:** FOX Sports product and ad sales (hypothetical audience for a portfolio project)
**From:** Simon Ngo, ASU W. P. Carey
**Re:** What the 2025 Cup season says about sponsor exposure, and a product idea

*Written from public data only. I have no knowledge of FOX's internal tools or plans; the ideas below may already exist in some form.*

## What the data shows

- **FOX's window carries the season.** In 2025, the first 12 races on FOX and FS1 held about half of the season's broadcast value for a back-of-field car, in a third of the races. A back-of-field start on the FOX broadcast network was worth roughly three times one on USA, driven entirely by audience.
- **Exposure is concentrated at the front.** Calibrated to the industry benchmark that the top 10 cars get about half of coverage, the top 10 capture about 40% of sponsor value across the season, and the car leading most laps gets about 13 times the clear logo time of a typical backmarker.
- **The long tail is where sponsorship is most fragile.** Part-time teams like NY Racing sell one race at a time to sponsors who get about 30–40 seconds of clear logo time per race. Those sponsors are most likely to leave the sport, and the teams they fund make up the field's depth.

## Why this matters to a broadcaster

Sponsor value on the car is a by-product of the broadcast, but it shapes who stays in the sport. A field full of well-funded cars and a stable Daytona 500 entry list are good for the product FOX broadcasts. FOX also sells to many of the same brands directly.

## Product idea: a per-race sponsor exposure report

FOX's production systems already know what is on screen, in timing data, graphics and camera assignments. A per-race report derived from that data, available to the ad sales team, could:

1. **Show sponsors exactly what their car received**, in seconds and ad-equivalent value, the week after the race, instead of waiting on third-party measurement.
2. **Support bundled packages** for part-time sponsors: a 30-second spot plus a guaranteed in-race feature (a "through the field" segment, a pit road graphic), so a small sponsor's spend covers both the car and the broadcast.
3. **Price the Daytona 500 window with qualification risk visible**, for example a spot package for a sponsor whose car might miss the race, with a make-good elsewhere in FOX's window.

## How I would build a first version

- **Phase 1 (this project):** public loop data, audiences, and a calibrated coverage model with Monte Carlo uncertainty. Static calculator, no backend.
- **Phase 2:** calibrate against hand-coded broadcast segments (protocol written), then an automated logo-detection model on broadcast frames, validated against the hand-coded set.
- **Phase 3:** scheduled ingest after each race, an API for sales tools, alerts when a report is late or looks anomalous. Architecture: a batch job per race, a small database, and the calculator as a front end; no real-time requirement.

The calculator and full method are in this repository.
