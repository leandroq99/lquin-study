# Ping-pong

Aplicação HTTP simples que responde `pong <n>` a cada requisição GET em `/pingpong`,
incrementando um contador mantido em memória.

Faz parte do curso **DevOps with Kubernetes** (exercício 1.9) e roda lado a lado com a
aplicação *Log output*, compartilhando o mesmo Ingress.

## Funcionamento

| Requisição            | Resposta     |
|-----------------------|--------------|
| `GET /pingpong` (1ª)  | `pong 0`     |
| `GET /pingpong` (2ª)  | `pong 1`     |
| `GET /qualquer-outro` | `404`        |

- O contador fica **em memória**: volta a `0` sempre que o pod é reiniciado.
- Apenas `/pingpong` incrementa o contador (ex.: `/favicon.ico` não conta).

## Configuração

| Variável | Padrão | Descrição                      |
|----------|--------|--------------------------------|
| `PORT`   | `3000` | Porta em que o servidor escuta |

## Executando localmente

Requer apenas Python 3 (sem dependências externas).

```bash
python3 app.py
curl localhost:3000/pingpong   # pong 0
curl localhost:3000/pingpong   # pong 1
```

## Docker

```bash
docker build -t <usuario>/ping-pong:1.9 .
docker run --rm -p 3000:3000 <usuario>/ping-pong:1.9
```

## Kubernetes

Os manifests ficam em `manifests/`:

- `deployment.yaml` — Deployment do ping-pong
- `service.yaml` — Service ClusterIP apontando para a porta do container
- `ingress.yaml` — regra `/pingpong` no Ingress compartilhado com o *Log output*

```bash
kubectl apply -f manifests/
curl localhost:8081/pingpong
```

> O cluster k3d foi criado com `-p 8081:80@loadbalancer`, então o Traefik (Ingress
> controller do k3s) fica acessível em `localhost:8081`.

Ajuste antes de usar:
- <usuario> e a tag da imagem.
- Nomes dos arquivos em manifests/: deixei a lista genérica, então troque pelos nomes que você realmente criar. Se você colocar a regra /pingpong dentro do ingress.yaml da Log output, em vez de criar um Ingress separado, remova o ingress.yaml dessa lista e mencione onde a regra está.
- Seção do Docker: ela supõe que existe um Dockerfile na pasta, igual ao da Log output.
