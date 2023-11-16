# Instructions


```
cd examples/chess/tomo
conda create --name chap-env python=3.10 mamba
conda activate chap-env
mamba install -c conda-forge -c  astra-toolbox chessanalysispipeline numpy nexusformat nexpy tomopy matplotlib lmfit astra-toolbox pydantic pip
python -m pip install --upgrade pip
python -m pip install pyspecs

CHAP ./pipeline.yaml


```