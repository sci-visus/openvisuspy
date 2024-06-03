#!/bin/bash

GIT_TAG=$(python3 ./scripts/new_tag.py)

git commit -a -m "New tag ($GIT_TAG)" 
git tag -a ${GIT_TAG} -m "${GIT_TAG}"
git push origin ${GIT_TAG}
git push origin