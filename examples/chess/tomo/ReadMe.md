# Instructions


Run the `tomo` jupyter notebook

Run the CHAP pipeline

```
cd examples/chess/tomo
conda create --name chap-env python=3.10 mamba
conda activate chap-env
mamba install -c conda-forge -c  astra-toolbox chessanalysispipeline numpy nexusformat nexpy tomopy matplotlib lmfit astra-toolbox pydantic==1.10.7 pip
python -m pip install --upgrade pip
python -m pip install certif-pyspec==1.5.3

CHAP ./out/pipeline.yaml


```