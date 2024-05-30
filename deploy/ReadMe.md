# Instructions

## Docker Compose

```bash

cd deploy

# Create an `.env` file with a token:
cat <<EOF > .env
NSDF_TOKEN=whatever-but-secure
EOF

# this is needed for WSL2
export ANSIBLE_CONFIG=${PWD}/ansible.cfg

sudo docker compose up chess1_service
sudo docker compose up chess2_service
sudo docker compose up jupyter_service
sudo docker compose up 
```

You can check if it's working going to any of the URL:

- http://localhost/
- http://localhost/chess1
- http://localhost/chess2
- http://localhost/lab

## Ansible

```bash

cd deploy

# Create an `.env` file with a token:
cat <<EOF > .env
NSDF_TOKEN=whatever-but-secure
EOF

# only needed for ansible (!)
cat <<EOF > ./inventory.ini
[all:vars]
ansible_ssh_connection=ssh 
ansible_ssh_user=root
ansible_ssh_private_key_file=~/.ssh/id_rsa

[my_vps]
127.0.0.1
EOF

# this is needed for WSL2
export ANSIBLE_CONFIG=${PWD}/ansible.cfg

# check connectivity
ansible all -m ping

# ansible-playbook options
#   --tags "configuration,packages"
#   --limit=<hostname>
#   -l <group-name>
#   -vvv

ansible-playbook ./setup.yml  # --tags "restart"

ansible-playbook ./benchmark.yml --verbose

# (OPTIONAL) Clean up notebooks
for it in $(find ./notebooks/*.ipynb) ; do
  jupyter nbconvert --clear-output --inplace ${it}
  jupyter trust ${it}
done

ansible-playbook ./run.yml  

# if you need to restart
ansible-playbook ./run.yml --tags restart -l 5.161.228.121

# if you need to check all services

# you can run it later...
# OPTIONAL, you can even use without precaching (cached=arco will cache blocks on demand)
ansible-playbook ./precache.yml                

# check docker ps
ansible --become-user root --become all -m shell -a 'cd /root/deploy && docker compose ps'  
ansible --become-user root --become all -m shell -a 'df -h'   | grep "/dev/sda1"
```

if you want to debug:

```
ssh -i <identity> root@vps-ip
cd deploy
docker ps
docker exec -it <service> bash
```