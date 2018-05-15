#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

# python libs
import xarray as xr
import numpy as np

# tk libs
from lib.io.matlab import ReadGowMat
from lib.KMA import KMA_simple
from lib.KMA import KMA_regression_guided
from lib.KMA import SimpleMultivariateRegressionModel as SMRM

# data storage
p_data = op.join(op.dirname(__file__),'..','data')

p_test = op.join(p_data, 'tests_KMA')
p_xds_pca_kmasimple = op.join(p_test, 'xds_PCA_KMASIMPLE.nc')

p_xds_pca_kmarg = op.join(p_test, 'xds_PCA_KMARG.nc')
p_mat_GOW = op.join(p_test, 'gow2_062_ 9.50_167.25.mat')

# --------------------------------------
# KMA SIMPLE

## Load PCA data from test file 
xds_PCA = xr.open_dataset(p_xds_pca_kmasimple)

# KMA simple
num_clusters = 6
repres = 0.95
xds_KMA = KMA_simple(
    xds_PCA, num_clusters, repres)



# --------------------------------------
# TODO KMA REGRESION GUIDED

# load PCA data from test file
xds_PCA = xr.open_dataset(p_xds_pca_kmarg)

# TODO: PARA ESTE TEST USAR DATOS PCA IDENTICOS A LOS DE MATLAB

# load GOW data from mat file
xds_GOW = ReadGowMat(p_mat_GOW)

# SIMPLE MULTIVARIATE REGRESION MODEL from GOW data
hs = xds_GOW.hs
tm = xds_GOW.t02
Fe = np.multiply(hs**2,tm)**(1.0/3)
xds_GOW.update({
    'Fe':(('time',), Fe)
})
xds_GOW = xds_GOW.sel(
    time=slice('1979-01-22','1980-12-31')
).resample(time='1D').mean()
xds_Yregres = SMRM(xds_PCA, xds_GOW, ['hs','t02','Fe'])


# KMA Regression Guided
num_clusters = 36
repres = 0.95
alpha = 0.3
xds_KMA = KMA_regression_guided(
    xds_PCA, xds_Yregres, num_clusters, repres, alpha)


# TODO: EN DEV SE USA UN BUCLE DE ALPHAS
#alpha = np.arange(0.1,1,0.1)

