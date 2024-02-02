
# Links

Home Page
- https://nsdf01.classe.cornell.edu/

id3a

- https://nsdf01.classe.cornell.edu/dashboards/umich/app/
- https://nsdf01.classe.cornell.edu/dashboards/capolungo-3850-a/app/

id4b

- https://nsdf01.classe.cornell.edu/dashboards/gopalan/app/
- https://nsdf01.classe.cornell.edu/dashboards/greven-3798-a/app/
- https://nsdf01.classe.cornell.edu/dashboards/lee-3565-c/app/
- https://nsdf01.classe.cornell.edu/dashboards/pagan-3579-c/app/
- https://nsdf01.classe.cornell.edu/dashboards/tian-3757-a/app/
- https://nsdf01.classe.cornell.edu/dashboards/gregory-3864-a/app/ (tracker running)
- https://nsdf01.classe.cornell.edu/dashboards/guo-3853-a/app/ (tracker running)


# Run dashboards

export an enviornment variable with the group name


Activate then enviroment:

```bash
conda activate nsdf-env
```

```bash
export NSDF_GROUP=<replace-with-group-name>
```

Create a screen session so you can reconnect later:

```bash
screen -S ${NSDF_GROUP}-dashboards
```

Use a version of code that is known to work (oct-nov-dec 2023)

```bash
git clone git@github.com:sci-visus/openvisuspy.git openvisuspy-chess-v0.1
cd openvisuspy-chess-v0.1
git checkout chess-v0.1
```

Setup python path:

```bash
export PYTHONPATH=./src/
```


Edit NGINX configuration file, and add the group app for the bokeh port

```bash
code /etc/nginx/nginx.conf
sudo /usr/bin/systemctl restart nginx
```

Setup and environment variable with the BOkeh port:

```bash
export BOKEH_PORT=<replace-with-group-port>

```
In case you need to set who has access or not to the dashboard, use this uids separated by `;` otherwise leave it emty or `*`

```bash

```
[OPTIONAL] add the group to the `index.html`

```bash
code /var/www/html/index.html
```


Create a cooking for bokeh encrypted communications:

```bash
export BOKEH_COOKIE_SECRET=$(echo $RANDOM | md5sum | head -c 32)
```

Run the dashboards:

```bash
while [[ "1" == "1" ]] ; do
python -m bokeh serve examples/dashboards/app \
   --port ${BOKEH_PORT} \
   --use-xheaders \
   --allow-websocket-origin='*.classe.cornell.edu' \
   --dev \
   --auth-module=./examples/chess/auth.py \
   --args 
   --prefer local
done
```

# [OPTIONAL] Run jobs manually (i.e. without the tracker)

To run manually jobs:

```bash
export NSDF_GROUP=...
rm -Rf tmp/*.json
python .workflow/${NSDF_GROUP}/run-convert.py 
```







