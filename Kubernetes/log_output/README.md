# log_output

Gera uma string aleatória (UUID) ao iniciar, guarda em memória e imprime a cada 5 segundos com timestamp.

```
2026-10-23T15:10:00.123Z: 8523ecb1-c716-4cb6-a044-b9e83bb98e43
```

## Como executar

Localmente:

```bash
python app.py
```

No Kubernetes:

```bash
docker build -t leandrocfg/log-output:1.1 .
docker push leandrocfg/log-output:1.1
kubectl apply -f manifests/deployment.yaml
kubectl logs -f deployment/log-output
```
