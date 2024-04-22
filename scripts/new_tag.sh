#!/bin/bash

#export PYPI_USERNAME="..."
#export PYPI_PASSWORD="..."

TAG=$(python3 scripts/new_tag.py) && echo ${TAG}

git commit -a -m "New tag ($TAG)" 
git tag -a $TAG -m "$TAG"
git push origin $TAG
git push origin

rm -f dist/*  
python3 -m build .

# this does not work in WSL2, use windows to just to the upload
python3 -m twine upload --username "${PYPI_USERNAME}"  --password "${PYPI_PASSWORD}" --non-interactive --verbose  --skip-existing --verbose "dist/*.whl" 