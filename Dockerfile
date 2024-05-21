FROM python:3.10

RUN python3 -m pip install --upgrade pip

COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt

ARG OPENVISUS_VERSION
RUN python3 -m pip install OpenVisusNoGui==$OPENVISUS_VERSION

ARG GIT_TAG
RUN python3 -m pip install openvisuspy==$GIT_TAG

RUN mkdir -p /home/notebooks

CMD ["jupyter", "lab", "--allow-root", "--notebook-dir='/home/notebooks'", "--port 8888", "--NotebookApp.token=''", "--NotebookApp.allow_origin='*'", "--ip", "0.0.0.0""]




