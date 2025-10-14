## Virtual Environment
```
conda create --name card-pipelines python=3.11
conda activate card-pipelines
cd $CONDA_PREFIX
mkdir -p ./etc/conda/activate.d
mkdir -p ./etc/conda/deactivate.d
vim ./etc/conda/activate.d/env_vars.sh
    cd path/to/date-pipelines/repo
    export MY_KEY='secret-key-value'

vim ./etc/conda/deactivate.d/env_vars.sh
    unset MY_KEY
```

## Docker
```
docker build -t card-pipelines:1.1.1 .
docker run -it --entrypoint sh card-pipelines:1.1.1
```
