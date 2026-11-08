# AI Corps: Group 4

The project, the AI Traffic-Safety Consultant (ATSC), lives in [ATSC/](ATSC/README.md): subsystems S1 to S4, the
integration pipeline (`ATSC/Makefile`), and the controlling documents in `ATSC/docs/`.
`Initial_Research/` holds early background notes.

## Run the website on a new machine (Ubuntu)

Paste this into a terminal. It installs Docker and git, pulls the latest code from GitHub (or
clones it the first time), builds the web app, and serves it at http://localhost:10000. The
model run and memos are already in the repo, so nothing else needs to run.

```bash
sudo apt update && sudo apt install -y docker.io git
sudo systemctl enable --now docker.socket docker.service
cd ~/Desktop
[ -d AICorps4 ] && git -C AICorps4 pull || git clone https://github.com/kabir-singh19/AICorps4.git
cd AICorps4/ATSC/S4_Web_App
sudo docker build -t atsc .
sudo docker rm -f atsc-demo 2>/dev/null
sudo docker run -d --name atsc-demo --restart unless-stopped -p 10000:10000 \
  -e ATSC_ENV=production -e ATSC_SESSION_SECRET="$(openssl rand -hex 32)" \
  -e ATSC_AI_ENABLED=false atsc
```

To update after new commits, run the same block again. The container restarts on its own after
a reboot.

- "Cannot connect to the Docker daemon": run `sudo systemctl start docker.socket docker.service`.
- Stop and remove: `sudo docker rm -f atsc-demo`. Remove Docker too: `sudo apt purge -y docker.io`.
- The full pipeline (database, model, memos) is in [ATSC/README.md](ATSC/README.md#build-and-run).

Notes from the 9/11 kickoff meeting. Project ideas are in [IDEAS.md](Initial_Research/IDEAS.md).

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
