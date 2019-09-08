# TESLA-KIT 

Python library for statistical calculations and methodologies for handling global climate data.

## Main contents


## Project Map

![picture](docs/img/map.svg)

## Documentation


## Install 
- - -

Source code is currently hosted on Bitbucket at: https://gitlab.com/ripollcab/teslakit/tree/master 

### Installing from sources

Install requirements. Navigate to the base root of [teslakit](./) and execute:


```
# requests module
pip install requests

# default python libraries 
pip install -r requirements/default.txt

# custom python libraries 
pip install -r requirements/extra.txt

# optional libraries (used for map plots)
pip install --user git+https://github.com/matplotlib/basemap.git

```

Then install teslakit

```
python setup.py install

# run pytest integration
python setup.py test
```



## Handling a Teslakit Project 
- - -

Jupyter notebook files can be found at [notebooks](scripts/notebooks)

start with [00_Set_Database.ipynb](scripts/notebooks/00_Set_Database.ipynb)


## Contributors


## Thanks also to


## License

This project is licensed under the MIT License - see the [license](LICENSE.txt) file for details




