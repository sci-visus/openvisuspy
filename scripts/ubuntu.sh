#!/bin/bash

python3 -m pip install --upgrade pip
python3 -m pip install hatch build keyring

# disable keyring
export PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring"
python3 -m keyring --disable

# will get the version from `pyproject.toml`
python3 -m build . --wheel
unzip -l dist/*.whl

# get OpenVisus version
python3 -m pip install --upgrade OpenVisusNoGui 
OPENVISUS_VERSION=$(python3 -c "from importlib.metadata import version;print(version('OpenVisusNoGui'))")

GIT_TAG=`git describe --tags --exact-match 2>/dev/null || true`

if [[ "${GIT_TAG}" != "" ]] ; then

  # publish to PyPi
  hatch publish --yes --no-prompt --user "${PYPI_USERNAME}" --auth "${PYPI_TOKEN}"

  # publish to DockerHub
  docker build --build-arg="OPENVISUS_VERSION=${OPENVISUS_VERSION}" --build-arg="GIT_TAG=${GIT_TAG}" --tag nsdf/openvisuspy:${GIT_TAG} ./
  echo ${DOCKER_TOKEN} | docker login -u=${DOCKER_USERNAME} --password-stdin
  docker push nsdf/openvisuspy:${GIT_TAG}
  docker push nsdf/openvisuspy:latest

fi
