# todo_app

Descrição: Servidor web; a porta é definida pela variável de ambiente PORT (padrão 3000).

## Como executar

```bash
docker build -t leandroq99/todo-app:1.2 .
docker push leandroq99/todo-app:1.2
kubectl apply -f manifests/
kubectl get pods
```
