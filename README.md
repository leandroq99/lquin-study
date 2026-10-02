# Estudo de Tecnologia — Homelab DevOps

Repositório pessoal de estudo e registro sobre infraestrutura, automação e DevOps. A maior parte do conteúdo ativo são **playbooks Ansible que operam um homelab real**, executados via **AWX** rodando dentro de um cluster Kubernetes.

## 🏠 Homelab

Todo o ambiente é provisionado localmente com **Vagrant + VirtualBox**, usando **Rocky Linux 9** em todas as VMs, numa rede privada `172.89.0.0/24`.

| VM | IP | vCPU / RAM | Função |
|----|----|-----------|--------|
| `master-1` | 172.89.0.11 | 2 / 4 GB | Control plane Kubernetes |
| `worker-1` | 172.89.0.21 | 2 / 4 GB | Worker Kubernetes |
| `worker-2` | 172.89.0.22 | 2 / 4 GB | Worker Kubernetes |
| `zabbix-server` | 172.89.0.30 | 2 / 2 GB | Monitoramento (Zabbix + MySQL) |
| `grafana` | 172.89.0.31 | 2 / 2 GB | Dashboards (Grafana) |
| `ipa-ldap` | 172.89.0.40 | — | Identidade centralizada (OpenLDAP / FreeIPA) |
| `dns-server` | 172.89.0.50 | 1 / 1 GB | DNS interno |

### Cluster Kubernetes

- **Kubernetes v1.30** (kubeadm), runtime **containerd**, 1 control plane + 2 workers
- **CNI:** Calico
- **Load Balancer:** MetalLB (pool em `172.89.0.24x`)
- **Ingress:** ingress-nginx (exposto via MetalLB)
- **Storage:** local-path-provisioner
- **Autoscaling / métricas:** metrics-server e Vertical Pod Autoscaler (VPA)
- **AWX** (via AWX Operator, PostgreSQL 15) — executa os playbooks deste repositório contra as VMs do lab

```
GitHub (este repo) ──push──► GitHub Actions ──API──► AWX (no K8s)
                                                       │ project sync
                                                       ▼
                                   Job Templates ──► dns / ldap / zabbix / grafana / nós K8s
```

## 🛠️ Tecnologias que estudo atualmente

- **Linux** (Rocky Linux / RHEL 9) — systemd, firewalld, dnf, SELinux
- **Kubernetes** — kubeadm, Calico, MetalLB, Ingress, storage, VPA
- **Ansible + AWX** — playbooks por serviço, Surveys, Vault, `target_hosts` dinâmico
- **Monitoramento** — Zabbix (server e agents) e Grafana
- **Serviços de infraestrutura** — DNS, OpenLDAP / FreeIPA
- **Docker / containers**
- **AWS** — EC2, AMI, Launch Templates e Auto Scaling automatizados com Ansible
- **CI/CD** — GitHub Actions disparando sync de projeto no AWX
- **IA aplicada a estudo** — geração de flashcards Anki com a API da Anthropic (Claude)

## 🚀 Próximos passos (roadmap de estudo)

- [ ] **ArgoCD** instalado no cluster, exposto via ingress-nginx
- [ ] **GitOps** — manifests/Helm charts versionados no Git como fonte da verdade, com ArgoCD fazendo o sync automático para o cluster
- [ ] Migrar workloads hoje aplicados manualmente (`kubectl apply`) para Applications do ArgoCD (padrão *app of apps*)
- [ ] Gerenciamento de segredos no fluxo GitOps (Sealed Secrets / External Secrets)
- [ ] Observabilidade nativa de Kubernetes (Prometheus + Grafana) complementando o Zabbix
- [ ] Integrar o ciclo Ansible/AWX (infra das VMs) com o ciclo GitOps (apps no cluster)

## 📁 Estrutura do repositório

- `Ansible/` — organizado por serviço, cada pasta com seus `templates/`, `vars/` e `scripts/`
  - `AWS/` — workflow de ciclo de vida EC2/ASG/AMI (playbooks `01-` a `08-` + `aws-ec2-ami-update.yml`)
  - `dns/` — registros DNS e configuração de clientes
  - `LDAP/` — cliente OpenLDAP (nslcd/authselect) e scripts de gestão de usuários/grupos
  - `zabbix/` — instalação do Zabbix server e agents (segredos via Ansible Vault)
  - `facts.yml` — coleta de facts ad-hoc
- `.github/workflows/` — sync automático do projeto no AWX a cada push
- `Docker/` — anotações de estudo de Docker
- `Anki/` — `anki_gen.py`, gerador de flashcards (PDF/Markdown → Anki) via API da Anthropic
- `wiki/` — espelho da wiki do GitHub
- `main1`, `main2`, `teste`, `file_fixes.yml`, `index.html` — rascunhos de estudo

## ▶️ Como usar

```bash
# Collections necessárias
ansible-galaxy collection install -r collections/requirements.yml

# Gerador de flashcards
python Anki/anki_gen.py arquivo.pdf --deck "Meu Deck"
```

Os playbooks são pensados para rodar pelo **AWX** (o inventário vive lá, não neste repo).

## Observações

Repositório voltado para estudo pessoal e aprendizado contínuo — atualizado conforme novos tópicos e experimentos são adicionados ao lab.
