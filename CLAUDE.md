# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This is a personal study/reference repository ("Estudo de Tecnologia" — see `README.md`) covering Docker, Ansible, and Anki flashcard generation. Despite the `hello-world` name, most of the active content is a set of Ansible playbooks that back a real home-lab: a 3-node Kubernetes cluster (Vagrant/VirtualBox, Rocky Linux 9) running AWX, which executes these playbooks against other lab VMs (DNS server, OpenLDAP/IPA, Zabbix, Grafana). The Vagrant/VirtualBox provisioning itself lives outside this repo.

Documentation and comments in this repo are written in **Portuguese** — keep new content consistent with that.

## Commands

- Install required Ansible collections: `ansible-galaxy collection install -r collections/requirements.yml` (needs `community.mysql`, `community.general`, `amazon.aws`).
- Anki flashcard generator: `python Anki/anki_gen.py <file.pdf|file.md> --deck "<name>" [--tags "..."] [--num-cards N] [--qtype 0|1|2] [--output out.csv]`. Requires `ANTHROPIC_API_KEY` env var (or `--api-key`) and `pip install anthropic pymupdf`. See `Anki/README_anki_gen.md` for question types and import steps.
- There is no local build/lint/test suite. `ansible.cfg` at the repo root sets `collections_path = ./` and enables the `ansible.posix.timer` callback (task duration in playbook output).

### Running the Ansible playbooks

These playbooks are designed to be run **by AWX** (project `AWX-PROJECT`, git-synced from this repo), not typically by hand from a workstation:
- There is no inventory file committed to this repo — inventory/hosts (`kubernetes_servers`, `monitoring`, `infrastructure`, `all_servers` groups; hosts like `master-1`, `worker-1`, `worker-2`, `zabbix-server`, `dns-server`, `ipa-ldap`, `grafana`) live only in AWX.
- `Ansible/zabbix/vars/secrets.yml` is **Ansible Vault-encrypted** — running `install_zabbix_server.yml` outside AWX requires `--ask-vault-pass`/`--vault-password-file` and the vault secret, which AWX holds as a credential.
- After pushing changes, AWX's copy of the repo is stale until its project is synced (`POST /api/v2/projects/<id>/update/`, or the sync button in the UI). A `push` to `main`/`leandroq99-patch-1` also triggers `.github/workflows/update_project_awx.yml`, which calls the AWX API to kick off that sync — but it needs `AWX_HOST`/`AWX_OAUTH_TOKEN` secrets and AWX's own outbound network access to GitHub to succeed.
- New/changed playbooks are invisible to AWX Job Templates until that project sync succeeds (AWX validates the playbook path against its last-synced checkout).

## Architecture

`Ansible/` is organized **per service**, each folder self-contained with its own `templates/`, `vars/`, and/or `scripts/` subdirectories:

- `Ansible/AWS/` — numbered playbooks (`01-...` to `08-...`) implementing an EC2/ASG/AMI lifecycle workflow (start template → snapshot → validate → stop → create AMI → update launch template → scale down/up), plus a consolidated `aws-ec2-ami-update.yml`.
- `Ansible/dns/` — DNS record and DNS-client configuration playbooks, with Jinja2 templates.
- `Ansible/LDAP/` — OpenLDAP client config (`config_openLDAP.yml`, nslcd/authselect-based) plus standalone shell scripts (`scripts/`) for LDAP user/group management.
- `Ansible/zabbix/` — Zabbix server and agent installation/config, with `templates/*.j2` and vault-encrypted `vars/secrets.yml`.
- `Ansible/facts.yml` — simple ad-hoc fact-gathering playbook.

**`target_hosts` pattern**: several playbooks (`facts.yml`, `Ansible/LDAP/config_openLDAP.yml`, `Ansible/zabbix/install_zabbix_agent.yml`) use `hosts: "{{ target_hosts | default('<group>') }}"` so AWX can point a single Job Template at different inventory groups/hosts at launch time (via a Survey or extra var), instead of hardcoding a target per playbook.

### Known pitfalls (found via real debugging in this lab)

- **Zabbix repo vs EPEL conflict**: installing `zabbix-*` packages from the official Zabbix repo on RHEL/Rocky 9 must pass `disablerepo: epel` to the `dnf` task — EPEL ships its own conflicting `zabbix-web` package, causing a depsolve error.
- **`Type=forking` services need a matching `PidFile`**: when a custom Jinja2 template fully replaces a service's config file (e.g. `zabbix_server.conf.j2`, `zabbix_agentd.conf.j2`), it must explicitly set `PidFile=` to the exact path the systemd unit's `PIDFile=` expects. If omitted, the daemon falls back to its compiled-in default path (often `/tmp/...`), systemd never finds the pidfile, and any `systemd: state=started/restarted` task on that service hangs in `activating` **forever** (no timeout) even though the process is actually running fine.
- **`firewalld` tasks need a guard on Kubernetes nodes**: `kubernetes_servers` hosts don't run `firewalld` (Calico/kube-proxy manage iptables directly), so a `firewalld:` task with `immediate: true` fails with "firewall is not currently running". Guard such tasks with a `service_facts` check (`when: 'firewalld.service' in ansible_facts.services and ansible_facts.services['firewalld.service'].state == 'running'`).

### Non-Ansible content

- `Docker/Docker_notes.txt` — plain-text study notes only, no code/scripts.
- `Anki/` — `anki_gen.py` (PDF/Markdown → Anki flashcards via the Anthropic API) plus its own README and example data files.
- `wiki/` — a mirror of the GitHub repo wiki; treat it as secondary/possibly stale documentation, not a source of truth for the current file layout (e.g. it still describes the AWS playbooks as living directly under `Ansible/`, not `Ansible/AWS/`).
- Root-level `main1`, `main2`, `teste`, `file_fixes.yml`, `index.html` are scratch/draft files from studying, not integrated with anything else in the repo.
