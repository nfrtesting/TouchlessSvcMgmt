# Touchless Service Management
deploy using `kubectl -n <namespaces> apply -f k8s-deploy`

This project provides a demonstration of using Prometheus, Grafana, and AlertManager as a configuration monitoring tool.  It deploys a single pod to a Kubernetes instance to perform the activities.  

The scrapers and dashboards are kept up to date using a sidecar pattern.  This sidecar in turn uses 2 secrets, one for dashboards, one for scrapers.  The sidecar does a git pull using the data from the secrets at a regular interval and pushes those dashboards and scrapers to the appropriate layer.  Only jsons in these gits persist across pod restarts.  For each, use anonymous/guest unless a login is required (put uid:pwd@ in the url)
* `kubectl -n <namespace> create secret generic dashboard-src --from-literal=url=<https://github.com/<user>/<repo>> `

Nodeports are used for exposing interfaces with Traefik ingress definitions provided as well.
Assuming that you edit /etc/hosts or have the ability to setup DNS, the following links apply to the ingress endpoints defined:
- http://prometheus.tsm 
- http://alertmanager.tsm 
- http://grafana.tsm (login is admin/admin)
- http://jenkins.tsm (login is admin/admin) 
- http://jupyter.tsm 
- http://robotics.tsm
- http://alertmonitor.tsm 
 

# Demo setup:
```
kubectl create namespace tsm
kubectl -n tsm create secret generic scraper-src --from-literal=url=https://github.com/wroney688/scrapers
kubectl -n tsm create secret generic dashboard-src --from-literal=url=https://github.com/wroney688/dashboards
kubectl -n tsm create secret generic jupyter-src --from-literal=url=https://github.com/wroney688/jupyter-packages
kubectl -n tsm create secret generic grafana-admin --from-literal=username=admin --from-literal=password=admin
kubectl -n tsm create secret generic jenkins-admin --from-literal=username=admin --from-literal=password=admin
kubectl -n tsm create secret generic robotics-config --from-literal=report-url=http://alertmonitor-web:5000/alert --from-literal=url=https://github.com/wroney688/poc
kubectl -n tsm apply -f k8s-deploy
kubectl -n tsm apply -f demonstration-deploy
```