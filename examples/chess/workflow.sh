#!/bin/bash

# //////////////////////////////////////////////////////////////////////////////////
function init_tracker() {

   convert_dir=${1? Error need a directory argument}

   if [ -d ${convert_dir} ]; then

      read -p "Are you sure you want to remove directory=${convert_dir}? (Y/n) " yn
      case ${yn} in 
         Y ) 
            echo ok, we will proceed
            ;;
         * ) 
            echo "skipping"
            return;;
      esac

      # remove directory
      rm  -Rf ${convert_dir} 
   fi

   # create the conversion directory
   mkdir -p ${convert_dir}

   # create emtpy files
   touch "${convert_dir}/convert.log"        
   touch "${convert_dir}/dashboards.log"
   touch "${convert_dir}/visus.group.config"
   touch "${convert_dir}/dashboards.json"

   # link the master visus config to the workflow directory (the tracker assume this name under the workflow folder)
   ln -f -s /mnt/data1/nsdf/OpenVisus/visus.config ${convert_dir}/visus.config #

   # add the dashboard json to Apache httpd so it can be served (for dashboards)
   group_name=$(basename ${convert_dir})
   ln  -f -s ${convert_dir}/dashboards.json ${WWW}/${group_name}.json 

   # make the job directory
   mkdir -p ${convert_dir}/jobs

   # create the db
   python  ./examples/chess/tracker.py create-db --convert-dir ${convert_dir} 
}

# //////////////////////////////////////////////////////////////////////////////////
function run_dashboards() {

   dashboards_config=${1? Error need a dashboard argument}
   bokeh_port=${2? Error need a bokeh port}

   # where to store the logs
   export OPENVISUSPY_DASHBOARDS_LOG_FILENAME=${dashboards_config/.json/.log}

   BOKEH_COOKIE_SECRET=$(echo $RANDOM | md5sum | head -c 32)

   python -m bokeh serve examples/dashboards/app \
      --port ${bokeh_port} \
      --use-xheaders \
      --allow-websocket-origin='nsdf01.classe.cornell.edu' \
      --dev \
      --auth-module=./examples/chess/auth.py \
      --args "${dashboards_config}" \
      --prefer local

}



