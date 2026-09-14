# Hardware Project Ideas

Every idea uses the same core kit: **Raspberry Pi 5 + AI HAT+ (Hailo accelerator)**.

Why this fits our track: many consultant contracts are "collect field data, then write a report." The Pi collects the data, the accelerator runs the ML model on the device, and the A&M chatbot API writes the report.

## How It Works

```
camera / sensors -> Pi 5 + AI HAT+ (ML on device) -> scores, counts, GPS -> database + map -> A&M LLM API -> report
```

Only results leave the device. No raw video is stored, so no faces or license plates.

---

## 1. Road Condition Scanner (top pick)

**What it does:** Mounts on a car and scores every street it drives.

**Hardware:** Pi 5, AI HAT+, Camera Module 3, USB GPS, accelerometer (IMU), car mount and power.

**ML:**
- YOLO detects cracks and potholes. Train on the public RDD2022 dataset, then fine-tune on local photos.
- Accelerometer vibration estimates road roughness.
- Both combine into a 0-100 condition score per street segment.

**LLM:** Writes a road condition report with a ranked repair list.

**Replaces:** Pavement condition surveys.

**How we prove it:** Compare our scores to the city's last consultant report, street by street.

**Extras:** Night drives can flag broken streetlights (the city runs its own electric utility). Long term, mount one on garbage trucks for weekly citywide scans.

## 2. Traffic and Pedestrian Counter

**What it does:** Mounts at an intersection and counts cars, bikes, and pedestrians, including which way they turn.

**Hardware:** Pi 5, AI HAT+, camera, weatherproof case, power.

**ML:** YOLO detection plus tracking (ByteTrack) gives counts and turning movements by time of day.

**LLM:** Writes a traffic study for an intersection or corridor.

**Replaces:** Traffic counts and traffic studies.

**How we prove it:** Hand-count one hour of footage and compare. Also compare to any existing city counts.

## 3. Building Thermal and Energy Audit

**What it does:** Scans city buildings for heat loss and energy waste.

**Hardware:** Pi 5, AI HAT+, thermal camera (MLX90640 is cheap, FLIR Lepton has more detail), regular camera, temperature/humidity/CO2 sensor.

**ML:**
- Finds hot and cold spots in thermal images: leaky windows, missing insulation, overheating electrical panels.
- Flags HVAC running in empty rooms (camera stores only people counts).

**LLM:** Writes an energy audit with fixes and estimated savings.

**Replaces:** Energy audit consultants.

**How we prove it:** Compare to a past audit or the building's utility bills.

## 4. Noise Monitor

**What it does:** Sits downtown or near complaint hotspots. Logs noise levels and identifies the source.

**Hardware:** Pi 5, AI HAT+, USB microphone, weatherproof case.

**ML:** A sound classifier (CNN on spectrograms, trained on UrbanSound8K) labels traffic, construction, music, and sirens, and logs decibel levels over time.

**LLM:** Writes a noise study, cross-checked with citizen complaints and survey data.

**Replaces:** Noise studies.

**How we prove it:** Check readings against a sound level meter.

---

## Comparison

| Idea | Difficulty | What we need from the city | Proof |
|---|---|---|---|
| Road scanner | Medium | Past road report; later, city vehicles | Consultant scores |
| Traffic counter | Medium | Permission to mount at an intersection | Hand counts |
| Thermal audit | Medium | Access to a city building | Past audit or utility bills |
| Noise monitor | Easy | Permission to place outdoors | Sound level meter |

## Notes

- **Budget:** base kit (Pi 5, AI HAT+, camera, SD card, power supply) is roughly $200-250. Check current prices.
- **Custom models:** compiling our own model for the AI HAT+ needs the Hailo Dataflow Compiler, which runs on an x86 Linux PC, not the Pi.

## Next Steps

1. Search the Open Checkbook for which of these studies the city pays for, and how much.
2. Ask Sam Rivera for past reports and permission for mounting or building access.
3. Ask the TAs about a hardware budget.
4. Pick one idea, order one kit, and get the model running on the bench before building the enclosure.
