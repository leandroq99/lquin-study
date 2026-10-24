# todo_app

Descrição: Servidor web; a porta é definida pela variável de ambiente PORT (padrão 5000).

## Como executar

```bash
docker build -t leandroq99/todo-app:1.5 .
docker push leandroq99/todo-app:1.5
kubectl apply -f manifests/
kubectl get pods
```
