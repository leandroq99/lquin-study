# Portal de Automação

Portal web para os times operacionais executarem job templates do AWX sem usar a console nem curl.
Os usuários entram com o login do LDAP/AD. O AWX vê um único usuário de serviço (dono do token),
e o portal decide quem pode executar o quê a partir dos grupos do LDAP.

```
app/main.py            backend FastAPI: sessão, permissões, catálogo, launch, status, histórico
app/auth.py            login no LDAP / Active Directory
app/static/index.html  interface (login → catálogo → formulário → execução / histórico)
Dockerfile             imagem publicada no Docker Hub pelo GitHub Actions
k8s/portal.yaml        Namespace, Deployment, Service e Ingress (portal.lab.local)
```

## Como funciona o acesso

```
Usuário ──login LDAP──► Portal ──token do svc-portal──► AWX
                          │
                          ├─ só mostra templates com a label "portal"
                          ├─ e liberados para um grupo do usuário (label "grupo:<grupo>")
                          └─ grava o usuário real em portal_user em cada execução
```

| Quem | O que vê e executa | Histórico |
| --- | --- | --- |
| Membro do grupo `portal-admins` | Todos os templates com a label `portal` | Execuções de todos |
| Demais usuários | Templates com `portal` + `grupo:<um grupo dele>` | Só as próprias |
| Usuário sem grupo liberado | Catálogo vazio | Vazio |

O usuário real vai para o AWX na variável `portal_user`. Ela é preenchida pelo backend a partir do login,
nunca pelo formulário. O portal também registra no log do pod cada login e cada execução.

## Publicar um template no portal

No AWX, no job template:

1. **Labels**: `portal` e um `grupo:<grupo do LDAP>` para cada grupo que pode usar
   (ex.: `grupo:linux-ops`). Sem label de grupo, só `portal-admins` enxerga.
2. **Survey** com as entradas do operador. Adicione também a pergunta **`portal_user`**
   (Text, opcional): o portal esconde esse campo e preenche com quem executou.
   Sem ela, a execução funciona, mas o AWX não registra o usuário e ela não aparece no histórico do usuário.
3. **Limit** com *Prompt on launch*, se o operador escolhe os servidores.
4. **Access**: papel **Execute** para o usuário de serviço do portal (`svc-portal`).

Se o playbook publicar `artifacts.results` (via `set_stats`, como o `Ansible/remote_command/run_command.yml`),
o portal mostra uma tabela por host; senão, mostra a saída do job (só o final, com botão de download).

## Build da imagem

Automático: todo push na `main` que altera `Portal/` dispara `.github/workflows/build_portal.yml`, que publica
`leandrocfg/portal-automacao:latest` e `leandrocfg/portal-automacao:<sha do commit>` no Docker Hub.
Secrets do repositório: `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN`.

## Deploy no cluster

```bash
# 1. Secret: token do AWX e chave da sessão (nunca no Git)
kubectl create namespace portal
kubectl -n portal create secret generic portal-awx \
  --from-literal=AWX_TOKEN='<token do svc-portal>' \
  --from-literal=PORTAL_SESSION_SECRET="$(openssl rand -base64 32)"

# 2. Aplicar e acompanhar
kubectl apply -f Portal/k8s/portal.yaml
kubectl -n portal rollout status deploy/portal
```

Acesse `http://portal.lab.local` (o nome aponta para o IP do ingress-nginx no MetalLB).
Depois de um push com mudanças no portal: `kubectl -n portal rollout restart deploy/portal`.

## LDAP: lab e AD corporativo

| Variável | Lab (OpenLDAP) | Active Directory |
| --- | --- | --- |
| `LDAP_URL` | `ldap://ipa-ldap.lab.local` | `ldaps://ad.empresa.com.br` |
| `LDAP_BIND_DN` | vazio (busca anônima) | conta de serviço, ex. `CN=svc-portal,OU=Servicos,DC=empresa,DC=com,DC=br` |
| `LDAP_BIND_PASSWORD` | — | no Secret `portal-awx` |
| `LDAP_USER_BASE` | `ou=People,dc=ipa,dc=local` | `OU=Usuarios,DC=empresa,DC=com,DC=br` |
| `LDAP_USER_FILTER` | `(uid={username})` | `(sAMAccountName={username})` |
| `LDAP_GROUP_BASE` | `ou=Groups,dc=ipa,dc=local` | `OU=Grupos,DC=empresa,DC=com,DC=br` |
| `LDAP_GROUP_FILTER` | padrão | `(member={user_dn})` (grupos aninhados: `(member:1.2.840.113556.1.4.1941:={user_dn})`) |
| `LDAP_NAME_ATTR` | `cn` | `displayName` |

O padrão de `LDAP_GROUP_FILTER` cobre `posixGroup` (`memberUid`), `groupOfNames` (`member`) e `groupOfUniqueNames`.
O AD normalmente não aceita busca anônima: use uma conta de serviço só de leitura.

## Outras variáveis

| Variável | Padrão | Uso |
| --- | --- | --- |
| `AWX_URL` | — | URL base do AWX; no cluster, o Service interno |
| `AWX_TOKEN` | — | Token do usuário de serviço (Secret `portal-awx`) |
| `AWX_API_PREFIX` | `/api/v2` | `/api/controller/v2` no AAP 2.5+ |
| `AWX_VERIFY_SSL` | `true` | `false` para certificado autoassinado |
| `PORTAL_LABEL` | `portal` | Label que publica o template |
| `PORTAL_GROUP_PREFIX` | `grupo:` | Prefixo das labels de grupo |
| `PORTAL_ADMIN_GROUP` | `portal-admins` | Grupo LDAP com acesso a todos os templates publicados |
| `PORTAL_USER_VAR` | `portal_user` | Pergunta do survey que recebe o usuário |
| `PORTAL_SESSION_SECRET` | aleatória | Chave do cookie de sessão; sem ela, todos deslogam a cada restart |
| `PORTAL_SESSION_HOURS` | `8` | Duração da sessão |
| `PORTAL_COOKIE_SECURE` | `false` | `true` quando o portal estiver em HTTPS |
| `PORTAL_HISTORY_SIZE` | `10` | Execuções no histórico |
| `PORTAL_STDOUT_MAX_KB` | `256` | Quanto da saída aparece na tela (a partir do fim) |

## Limites desta versão

- Login por usuário e senha (bind LDAP). SSO (OIDC/SAML com Entra ID/ADFS) fica para a versão de produção.
- O portal está em HTTP no lab: a senha trafega sem criptografia entre o navegador e o ingress.
  Em produção, use HTTPS no Ingress e `PORTAL_COOKIE_SECURE=true`, e `ldaps://` para o LDAP.
