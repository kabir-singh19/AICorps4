# Project Ideas

Each idea is an autonomous system: custom hardware, deep learning, and autonomy. Each one does work the city currently pays inspectors or consultants for, then generates the report.

## Common Setup

- **Compute:** Raspberry Pi 5 (8GB) + AI HAT+ (Hailo) runs perception, deep learning, and autonomy.
- **Real-time control:** a flight controller or a microcontroller on our motor board drives the motors.
- **Reports:** the A&M chatbot API turns the robot's results into the report a consultant would deliver.
- **Custom models:** compiling our own models for the AI HAT+ needs the Hailo Dataflow Compiler on an x86 Linux PC.

## Summary

| # | Idea | Where it works | Hardest part | Main risk |
|---|---|---|---|---|
| 1 | Power line inspection drone | Air | Wire following, magnetic distance sensing | Flight approval |
| 2 | Sewer and storm drain robot | Inside pipes | Navigation without GPS, tether design | Waterproofing |
| 3 | Sidewalk inspection rover | Sidewalks | Navigation around people, 3D hazard measurement | Public safety |
| 4 | Autonomous survey boat | Ponds, lakes | Custom sonar | Waterproofing |
| 5 | Robotic waste audit station | Lab / facility | Grasping moving items, custom NIR sensor | Messy objects |

---

## 1. Power Line Inspection Drone

**What it does:** Flies along city power lines on its own and inspects every pole.

**Autonomy:** Flies GPS waypoints to the line, then follows the wires using a wire-segmentation network. Keeps a safe distance using stereo depth and magnetic field sensing.

**Deep learning / CV:**
- Detects insulators, crossarms, and transformers
- Classifies damage: cracked insulators, corrosion, leaning poles, bird nests
- Measures tree distance to the lines from depth
- Finds hot spots with a thermal camera

**EE build:**
- Magnetic sensor board that estimates distance to live wires from their field. The ratio between two sensors a known distance apart gives distance regardless of current.
- Custom power distribution board
- Time-synced cameras, thermal camera, and IMU
- Flight controller integration

**Hardware:** drone frame, motors, ESCs, LiPo battery, flight controller (PX4 or ArduPilot), GPS, 2x Pi Global Shutter Camera (stereo), thermal camera, custom magnetic sensor board, telemetry radio, RC transmitter for manual override, Remote ID module (FAA requirement).

**Output:** Report for each pole with photos, GPS location, and severity.

**Replaces:** Line inspection and vegetation management surveys.

**How we prove it:** Compare our findings to a utility crew's manual inspection of the same poles.

**Risk:** Needs an FAA Part 107 license and utility approval. Develop on a mock pole and wire setup first.

## 2. Sewer and Storm Drain Inspection Robot

**What it does:** A waterproof robot that drives inside pipes and grades their condition.

**Autonomy:** No GPS in a pipe. Tracks position with wheel encoders, IMU, and visual odometry, so every defect is tagged by distance. Stops at defects automatically and handles debris.

**Deep learning / CV:**
- Detects cracks, roots, offset joints, and water leaking in. Train on Sewer-ML (1.3M public sewer images).
- Codes defects to NASSCO PACP, the industry standard
- Laser ring + camera measures pipe deformation in 3D

**EE build:**
- Sealed motor drives and LED lighting driver
- Laser ring projector
- Pan/tilt camera head
- Power and data over one long tether (voltage drop, long-cable data link)

**Hardware:** waterproof tracked or 4WD chassis, DC motors with encoders, custom motor driver board, sealed camera housing with Pi Camera Module 3 (Wide), pan/tilt servos, LED ring, laser diode with ring optic, IMU, leak sensor, tether cable and reel with length encoder, surface power station.

**Output:** Condition report ranking pipe segments for repair.

**Replaces:** Pipe camera inspection contractors and condition assessment consultants.

**How we prove it:** Compare our defect codes to a certified inspector's report on the same pipe.

**Risk:** Waterproofing. Test in a pipe section in the lab first. City crews are needed for manhole access.

## 3. Sidewalk Inspection Rover

**What it does:** A ground robot that drives city sidewalks and maps ADA problems.

**Autonomy:** RTK GPS plus visual-inertial odometry, path planning along sidewalks, and avoidance of pedestrians and obstacles.

**Deep learning / CV:**
- Segments the sidewalk and finds cracks, obstructions, and missing curb ramps
- Measures trip hazards (height jumps between slabs) in 3D from stereo depth
- Measures slope with the IMU against ADA limits

**EE build:**
- Custom motor driver PCB with encoders and current sensing
- Battery management and power board
- Hardware-synced stereo cameras on the Pi 5's two camera ports
- E-stop safety circuit

**Hardware:** rover chassis, DC motors with encoders, custom motor driver PCB, battery pack with BMS, RTK GPS module and antenna, IMU, 2x Pi Global Shutter Camera (stereo), microcontroller for motor control, physical and wireless e-stop.

**Output:** Map and report of every ADA violation.

**Replaces:** Sidewalk and curb ramp surveys for the city's ADA transition plan.

**How we prove it:** Compare to manual measurements (digital level and ruler) on sample blocks.

**Risk:** Operates around the public, so a team member follows it.

## 4. Autonomous Survey Boat

**What it does:** Maps the city's stormwater ponds and lakes on its own.

**Autonomy:** GPS + IMU navigation, full-coverage route planning around the shoreline, obstacle avoidance, holding position in wind, and return home on low battery or lost signal.

**Deep learning / CV:**
- Segments shoreline and obstacles for navigation
- Detects algae blooms, floating trash, invasive plants, and bank erosion

**EE build:**
- Custom sonar: high-voltage transducer driver, receiver with preamp, bandpass filter, and time-varying gain, plus echo processing for depth
- Isolated water quality sensor board (probes in the same water interfere without isolation)
- Twin-thruster motor control, sealed electronics, telemetry radio

**Hardware:** catamaran hull, 2x brushless thrusters with ESCs, battery, GPS, IMU, sonar transducer, custom sonar board, pH / dissolved oxygen / turbidity / conductivity / temperature probes, custom isolated sensor board, Pi Camera Module 3, controller running ArduPilot Rover (boat mode), telemetry radio.

**Output:** Depth map showing sediment buildup, plus a water quality report.

**Replaces:** Sediment surveys for dredging planning and manual water sampling.

**How we prove it:** Compare sonar depths to manual depth-pole readings, and sensor readings to a calibrated handheld meter.

**Risk:** Waterproofing. Test in a pool first.

## 5. Robotic Waste Audit Station

**What it does:** A conveyor belt with a robot arm that sorts a sample of city trash and recycling and reports what's in it.

**Robotics:**
- Vision-guided picking: detect item, find grasp point from depth, time the arm to grab it off the moving belt
- Suction gripper with a pressure sensor to confirm each grab

**Deep learning / CV:**
- Segments and labels items: plastic, paper, glass, metal, food, contamination. Train on the ZeroWaste and TACO datasets.
- Combines camera and NIR readings to tell plastic types apart (PET, HDPE, PP)

**EE build:**
- Custom NIR spectrometer: NIR LEDs, InGaAs photodiodes, transimpedance amplifiers, lock-in detection to reject room light
- Load cell to weigh each item (waste audits report by weight)
- Conveyor speed control with encoder for pick timing
- Arm motor drivers

**Hardware:** conveyor belt with motor and encoder, 4-6 axis robot arm, vacuum pump, suction cup, pressure sensor, 2x Pi Global Shutter Camera (stereo depth), Pi Camera Module 3, NIR LEDs, InGaAs photodiodes, custom amplifier board, load cell with ADC board, microcontroller for arm and conveyor, enclosed lighting box.

**Output:** Report of each material's share by weight, contamination rate, and trends.

**Replaces:** Waste characterization consultants who sort sample bins by hand.

**How we prove it:** Hand-sort the same sample and compare results by weight.

**Risk:** Grabbing dirty, soft items is hard. Start with dry recyclables.

---

## Next Steps

1. Ask Sam Rivera whether drone flights near city power lines could be approved. If yes, the drone is the top pick. If not, the pipe robot.
2. Ask what the city owns and inspects (sewers, storm drains, ponds, recycling program) and for past reports we can compare against.
3. Search the Open Checkbook for which of these services the city pays for.
4. Pick one, get the Pi 5 + AI HAT+ running the perception model on the bench while the hardware is designed.
