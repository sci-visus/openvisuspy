#!/bin/bash

python3 -m pip install --upgrade pip
python3 -m pip install hatch build keyring

# disable keyring
export PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring"
python3 -m keyring --disable

# will get the version from `pyproject.toml`
python3 -m build . --wheel
unzip -l dist/*.whl

# publish only if there is a tag
GIT_TAG=`git describe --tags --exact-match 2>/dev/null || true`
if [[ "${GIT_TAG}" != "" ]] ; then

  # PyPi
  hatch publish --yes --no-prompt --user "${PYPI_USERNAME}" --auth "${PYPI_TOKEN}"

  # DockerHub
  if [[ "${PYTHON_VERSION}" == "3.10" ]] ; then
    docker build --build-arg="GIT_TAG=${GIT_TAG}" --tag nsdf/openvisuspy:${GIT_TAG} --tag nsdf/openvisuspy:latest ./
    docker push nsdf/openvisuspy:${GIT_TAG}
    docker push nsdf/openvisuspy:latest
  fi

fi
