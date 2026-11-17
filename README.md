# AI Corps: Group 4

The project, the AI Traffic-Safety Consultant (ATSC), lives in [ATSC/](ATSC/README.md): subsystems S1 to S4, the
integration pipeline (`ATSC/Makefile`), and the controlling documents in `ATSC/docs/`.
`Initial_Research/` holds early background notes.

Notes from the 9/11 kickoff meeting. Project ideas are in [IDEAS.md](Initial_Research/IDEAS.md).

## Run the website on a new machine

Each block below installs what is missing, pulls the latest code from GitHub (or clones it the
first time), builds the web app with Docker, and serves it at http://localhost:10000. The model
run and memos are already in the repo, so nothing else needs to run. To update after new
commits, run the same block again. The container restarts on its own whenever Docker starts.

### Ubuntu

Paste into a terminal:

```bash
sudo apt update && sudo apt install -y docker.io git
sudo systemctl daemon-reload; sudo systemctl reset-failed docker.socket docker.service
sudo systemctl enable docker.socket docker.service && sudo systemctl restart docker.socket docker.service
cd ~/Desktop
[ -d AICorps4 ] && git -C AICorps4 pull || git clone https://github.com/kabir-singh19/AICorps4.git
cd AICorps4/ATSC/S4_Web_App
sudo docker build -t atsc .
sudo docker rm -f atsc-demo 2>/dev/null
sudo docker run -d --name atsc-demo --restart unless-stopped -p 10000:10000 \
  -e ATSC_ENV=production -e ATSC_SESSION_SECRET="$(openssl rand -hex 32)" \
  -e ATSC_AI_ENABLED=false atsc
```

- "Cannot connect to the Docker daemon": run `sudo systemctl restart docker.socket docker.service`, then paste the whole block again.
- Stop and remove: `sudo docker rm -f atsc-demo`. Remove Docker too: `sudo apt purge -y docker.io`.

### macOS (Intel or Apple Silicon)

One-time setup: install git with `xcode-select --install`, and install
[Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) (or
`brew install --cask docker` if you use Homebrew). Open Docker Desktop once and wait until it
says it is running. Then paste into Terminal:

```bash
cd ~/Desktop
[ -d AICorps4 ] && git -C AICorps4 pull || git clone https://github.com/kabir-singh19/AICorps4.git
cd AICorps4/ATSC/S4_Web_App
docker build -t atsc .
docker rm -f atsc-demo 2>/dev/null
docker run -d --name atsc-demo --restart unless-stopped -p 10000:10000 \
  -e ATSC_ENV=production -e ATSC_SESSION_SECRET="$(openssl rand -hex 32)" \
  -e ATSC_AI_ENABLED=false atsc
```

### Windows 10 or 11

One-time setup, in PowerShell:

```powershell
winget install -e --id Git.Git
winget install -e --id Docker.DockerDesktop
```

Restart the PC if the installer asks (Docker Desktop turns on WSL 2), then open Docker Desktop
once and wait until it says it is running. Open a new PowerShell window and paste:

```powershell
cd $HOME
if (Test-Path AICorps4) { git -C AICorps4 pull } else { git clone https://github.com/kabir-singh19/AICorps4.git }
cd AICorps4\ATSC\S4_Web_App
docker build -t atsc .
docker rm -f atsc-demo 2>$null
$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$secret = -join ($b | ForEach-Object { '{0:x2}' -f $_ })
docker run -d --name atsc-demo --restart unless-stopped -p 10000:10000 `
  -e ATSC_ENV=production -e ATSC_SESSION_SECRET=$secret `
  -e ATSC_AI_ENABLED=false atsc
```

### All platforms

- Docker errors such as "cannot connect" or "pipe not found" on macOS or Windows mean Docker
  Desktop is not running. Open it, wait, and run the block again.
- Port 10000 already in use: change `-p 10000:10000` to `-p 8080:10000` and open
  http://localhost:8080.
- Stop and remove the site: `docker rm -f atsc-demo` (add `sudo` on Ubuntu).
- The full pipeline (database, model, memos) is in [ATSC/README.md](ATSC/README.md#build-and-run).

## Run the road evaluator (terminal tool)

A command-prompt style tool that runs the S2 crash-risk model on any College Station road. It needs no
Docker and no database, only Python 3.11 or newer (https://www.python.org/downloads/; on Windows tick
"Add python.exe to PATH"). The first run sets up its own environment in `demo/.venv` (about a minute,
needs internet once); later runs start in a few seconds and work offline.

### Install

Get the repo with `git clone https://github.com/kabir-singh19/AICorps4.git`, or on GitHub click
Code > Download ZIP and unzip it. Then start the tool:

- **macOS / Linux:** `bash AICorps4/ATSC/S2_Risk_Model_Backtest/demo/atsc.sh`
- **Windows:** double-click `AICorps4\ATSC\S2_Risk_Model_Backtest\demo\atsc.bat`, or run that path in
  Command Prompt. Windows Terminal shows the colors best.

On a Mac, if it says LightGBM could not load, run `brew install libomp` and start it again.

### Use

At start-up it reloads the 18 saved models, recomputes all 6,656 sites and checks the ranking hash
against the frozen run (OK in green, MISMATCH in red).

At the `C:\ATSC>` prompt:

| Type | Does |
|---|---|
| a road name or site ID (`holleman`, `texas ave`, `17683`) | lists matching sites, highest risk first |
| `top` | the 15 highest-risk sites |
| `hin` | ATSC vs HIN scoreboard |
| `exit` | quit |

In a results list, type a number to open a site, `b` to go back, or a new search. A site screen shows
its rank, ATSC flag, HIN membership, the model pipeline numbers, the top factors (red raises risk, green
lowers it) and how the model frozen at 2022 did on 2023-2025. Keys on a site screen:

| Key | Does |
|---|---|
| `1` | change a feature (traffic, speed, lanes, signals, crossings...) and re-run the models |
| `2` | traffic +50% |
| `3` | remove or add the signal (intersections) or speed -10 mph (segments) |
| `4` | crash history 2016-2025 |
| `5` | the full math for the site |
| `6` | compare with another road |
| `7` | ATSC vs HIN scoreboard |
| `r` | reset your changes |
| `b` | back to the list (or type any road name to search again) |
| `q` | quit |

More detail is in [ATSC/S2_Risk_Model_Backtest/demo/README.md](ATSC/S2_Risk_Model_Backtest/demo/README.md).

## Project: AI Consulting Tool (Teams 1 & 4)

Goal: reduce the city's reliance on paid outside consultants (currently about 40) with an LLM-based consulting tool.
Core question: Can an LLM-based consulting tool reduce the City's reliance on outside consulting by reproducing selected 
consulting deliverables at comparable quality and substantially lower cost?

- Most of the city's expertise comes from outside. Figure out the consultant budget.
- Build an expertise network: which consultants the city uses, and for what.
- Use the tool to respond to RFPs/RFQs the way a consulting firm would.
- Show the comparison: what a consultant delivered (and was paid) vs. what our AI generates.

## Data Sources

- Open Checkbook: all city transactions, vendor list (search by name)
- Budget and operations data
- Citizen surveys
- Taxes (6.25%)
- Other open sources the city has (mostly public data)
- Not using: warrants, emergency calls

## City Structure

- Elected officials: separate department
- City Manager
  - COO: fire, police, electric utilities
  - CIO: reports to CFO
- Contacts: Allison, Sam Rivera (main contact)

## Approach

- It's a service; it may or may not be a website. Scope will change as needs grow.
- Build on the city's existing tools: organized prompting of the A&M chatbots through the API with tokens, not the A&M interface. Learn what they can and can't do.
- Architect solutions with pre-existing models and data.
- Talk to someone at the city about data we need but don't have.
- API charges are covered; get approval before going over budget.

## Timeline

- Sept 17: CONOPS due ✅
- In a few weeks: go to City Hall and explain what we'll do and what the city needs to do
- End of spring: present to City Council (per Sam Rivera)
- Oct 1: FSR, ICD due

## Team Notes

- About 10 days behind
- Competing with Team 1
- Compare our AIs answers with the actual consulting experts solutions.
- Meet at least once every other week; keep TAs involved
- TA with the most experience in AI Sabyasachi Gupta — sabyasachi.gupta@tamu.edu
