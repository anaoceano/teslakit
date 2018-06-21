#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

import numpy as np
import matplotlib.pyplot as plt
import xarray as xr

# tk libs
from lib.io.matlab import ReadMatfile
from lib.PCA import CalcPCA_EstelaPred
from lib.plotting.EOFs import Plot_EOFs_EstelaPred

# data storage
p_data = op.join(op.dirname(__file__), '..', 'data')
p_test = op.join(p_data, 'tests', 'tests_estela', 'test_estela_PCA')

# use teslakit test data 
p_estela_pred = op.join(p_test, 'xds_SLP_estela_pred.nc')
xds_SLP_estela_pred = xr.open_dataset(p_estela_pred)

# Calculate PCA
xds_PCA = CalcPCA_EstelaPred(xds_SLP_estela_pred, 'SLP')
xds_PCA.to_netcdf(op.join(p_test, 'xds_SLP_PCA.nc'))
print xds_PCA


# Plot EOFs
n_plot = 3
p_save = op.join(p_test, 'Plot_EOFs_EstelaPred')
Plot_EOFs_EstelaPred(xds_PCA, n_plot, p_save)


