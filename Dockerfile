FROM python:3.10

RUN python3 -m pip install --upgrade pip

COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt

RUN python3 -m pip install --upgrade OpenVisusNoGui

ARG GIT_TAG
RUN python3 -m pip install openvisuspy==$GIT_TAG

CMD ["jupyter", "lab", "--allow-root", "--notebook-dir='/usr/local/lib/python3.10/site-packages/openvisuspy/notebooks'", "--port 8888", "--NotebookApp.token=''", "--NotebookApp.allow_origin='*'", "--ip", "0.0.0.0""]




