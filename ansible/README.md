# Instructions

```bash

ansible all -m ping

# --tags "configuration,packages"
# --limit=<hostname>
# l <group-name>
# -vvv
ansible-playbook ./playbooks/setup-node.yml 

# OPTIONAL, benchmark node
ansible-playbook ./playbooks/benchmark-node.yml

# Example of how running a command:
ansible --become-user root --become all -m shell -a 'docker ps'

# Example of how to generate short urls:
for it in $(ansible  all  --list-hosts | tail -n +2); do 
  echo $(python3 scritps/shorten.py "http://$it:8888") "http://$it:8888"
done

# clean up notebooks
for it in $(find deploy/notebooks/*.ipynb) ; do
  echo ${it}
  jupyter nbconvert --clear-output --inplace ${it}
  jupyter trust ${it}
done

# Optional: Remove all containers:
ansible-playbook ./playbooks/remove-containers.yml 

# deploy 
ansible-playbook ./playbooks/deploy-node.yml 

```

