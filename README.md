# Touchless Service Management
deploy using `kubectl -n <namespaces> apply -f k8s-deploy`

This project provides a demonstration of using Prometheus, Grafana, and AlertManager as a configuration monitoring tool.  It deploys a single pod to a Kubernetes instance to perform the activities.  

The scrapers and dashboards are kept up to date using a sidecar pattern.  This sidecar in turn uses 2 secrets, one for dashboards, one for scrapers.  The sidecar does a git pull using the data from the secrets at a regular interval and pushes those dashboards and scrapers to the appropriate layer.  Only jsons in these gits persist across pod restarts.  For each, use anonymous/guest unless a login is required (put uid:pwd@ in the url)
* `kubectl -n <namespace> create secret generic dashboard-src --from-literal=url=<https://github.com/<user>/<repo>> `
* `kubectl -n <namespace> create secret generic scraper-src --from-literal=url=<https://github.com/<user>/<repo>>`

Nodeports are used for exposing interfaces with Traefik ingress examples provided as well. 
## Prometheus Configuration
Pulls a prometheus.yml from the scraper-src secret's repository.


 
## Grafana Configuration
The Grafana administrative user is set using a secret in the namespace.  To create the secret use: `kubectl create secret generic grafana-admin --from-literal=username=<username> --from-literal=password=<password>`

UI exposed as configmon-grafana-web.  Configuration is held in a ConfigMaps defined in configmon_grafana.yml.  configmon-grafana-config holds the actual configuration for grafana (where to find dashboards and the prometheus datasource definition).  

## AlertManager Configuration
UI exposed as configmon-alertmanager-web.  Configuration is held in two ConfigMaps.  configmon_alertmanager_config.yml contains the alertmanager configuration while configmon_alertmanager_templates.yml holds the alerting templates.

## Webhook Configuration
Configuration contained in configmon-webhook.yml and stored in a single ConfigMap (source code, python).  Requires a secret: `kubectl create secret generic webhook-bot-config --from-literal=url=<url> --from-literal=botid=<botid> --from-literal=password=<botpwd>`

# Demo setup:
```
kubectl create namespace tsm
kubectl -n tsm create secret generic scraper-src --from-literal=url=https://github.com/wroney688/scrapers
kubectl -n tsm create secret generic dashboard-src --from-literal=url=https://github.com/wroney688/dashboards
kubectl -n tsm create secret generic grafana-admin --from-literal=username=tsm --from-literal=password=ScottRulez!
kubectl -n tsm create secret generic webhook-bot-config --from-literal=url=http://alertmonitor-web:5000/alert --from-literal=botid=i_am --from-literal=password=not_used
kubectl -n tsm apply -f k8s-deploy
kubectl -n tsm apply -f demonstration-deploy
```