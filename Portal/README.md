# Portal de Automação

Portal web para os times operacionais executarem job templates do AWX sem usar a console nem curl.
O navegador só fala com o portal; só o portal (backend) fala com a API do AWX e guarda o token.

```
app/main.py            backend FastAPI (catálogo, formulário, launch, status, stdout)
app/static/index.html  interface (catálogo → formulário → execução)
Dockerfile             imagem publicada no Docker Hub pelo GitHub Actions
k8s/portal.yaml        Namespace, Deployment, Service e Ingress (portal.lab.local)
```

## Como um template aparece no portal

No AWX, o job template precisa:

- ter a label **`portal`**;
- receber as entradas do operador só por **Survey** (e **Limit** com *Prompt on launch*, se fizer sentido);
- ser executável pelo usuário dono do token do portal (papel **Execute**).

O formulário é gerado a partir do survey.

A tela **Histórico** mostra as últimas execuções feitas pelo portal, consultando o próprio AWX (jobs criados pelo usuário do token): não há banco de dados no portal. Cada execução tem um link direto (`/#job-<id>`). Saídas grandes aparecem cortadas na tela (só o final) e podem ser baixadas inteiras.

Se o playbook publicar `artifacts.results` (via `set_stats`, como o `Ansible/remote_command/run_command.yml`), o portal mostra uma tabela por host; senão, mostra o stdout do job.

## Build da imagem

Automático: todo push na `main` que altera `Portal/` dispara `.github/workflows/build_portal.yml`, que publica
`<usuário>/portal-automacao:latest` e `<usuário>/portal-automacao:<sha do commit>` no Docker Hub.

Secrets necessários no repositório: `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN` (access token do Docker Hub).

## Deploy no cluster

```bash
# 1. Namespace e token do AWX (o token nunca vai para o Git)
kubectl create namespace portal
kubectl -n portal create secret generic portal-awx --from-literal=AWX_TOKEN='<token do AWX>'

# 2. Confira o AWX_URL em k8s/portal.yaml (imagem: leandrocfg/portal-automacao)
kubectl get svc -n awx            # nome do Service do AWX

# 3. Aplique
kubectl apply -f Portal/k8s/portal.yaml
kubectl -n portal rollout status deploy/portal
```

Acesse `http://portal.lab.local`. O nome precisa resolver para o IP do ingress-nginx no MetalLB
(`kubectl get svc -n ingress-nginx`): adicione no `dns-server` do lab ou no `hosts` do seu PC.

Atualizar para a imagem nova depois de um push:

```bash
kubectl -n portal rollout restart deploy/portal
```

## Variáveis

| Variável | Padrão | Uso |
| --- | --- | --- |
| `AWX_URL` | — | URL base do AWX; no cluster, o Service interno |
| `AWX_TOKEN` | — | Token do usuário do portal (Secret `portal-awx`) |
| `AWX_API_PREFIX` | `/api/v2` | `/api/controller/v2` no AAP 2.5+ |
| `AWX_VERIFY_SSL` | `true` | `false` para certificado autoassinado |
| `PORTAL_LABEL` | `portal` | Label que publica o template no catálogo; vazio = todos |
| `PORTAL_HISTORY_SIZE` | `10` | Quantas execuções aparecem em Histórico |
| `PORTAL_STDOUT_MAX_KB` | `256` | Quanto da saída do job aparece na tela (a partir do fim); o resto fica no botão de download |

## Limites desta versão

- Sem login: qualquer pessoa que alcance o portal executa com o token dele. Use só dentro do lab.
- Todas as execuções aparecem no AWX como o usuário do token.
