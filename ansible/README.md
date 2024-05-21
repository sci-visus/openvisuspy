# Instructions

Debug locally:

```bash 
cd ansible

ln -s ../notebooks /mnt/data/notebooks

sudo docker-compose up chess1_service
sudo docker-compose up chess2_service
sudo docker-compose up jupyterlab_service

# all together
sudo docker-compose up 
# http://127.0.0.1/
# http://127.0.0.1/chess1
# http://127.0.0.1/chess2
```

Deploy with ansible:

```bash

cd ansible

# this is needed for WSL2
export ANSIBLE_CONFIG=$PWD/ansible.cfg

# check connectivity
ansible all -m ping

# once only after VPS creation
#   --tags "configuration,packages"
#   --limit=<hostname>
#   -l <group-name>
#   -vvv
ansible-playbook ./playbook-setup-node.yml 

# (OPTIONAL) benchmark node
ansible-playbook ./playbook-benchmark-node.yml

# (OPTIONAL) Run single command
ansible --become-user root --become all -m shell -a 'docker ps'

# (OPTIONAL) Generate short urls
for it in $(ansible  all  --list-hosts | tail -n +2); do 
  echo $(python3 scritps/shorten.py "http://$it:8888") "http://$it:8888"
done

# (OPTIONAL) clean up notebooks
for it in $(find ./notebooks/*.ipynb) ; do
  jupyter nbconvert --clear-output --inplace ${it}
  jupyter trust ${it}
done

# (OPTIONAL) Remove all containers:
ansible-playbook ./playbook-remove-containers.yml 

# (OPTIONAL) deploy 
ansible-playbook ./playbook-deploy-node.yml 
```

