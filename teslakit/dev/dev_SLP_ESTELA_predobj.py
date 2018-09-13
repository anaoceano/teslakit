#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

import numpy as np
import xarray as xr

# tk libs
from lib.objs.predictor import Predictor
from lib.io.matlab import ReadGowMat, ReadCoastMat, ReadEstelaMat
from lib.estela import spatial_gradient, mask_from_poly

# data storage
p_data = op.join(op.dirname(__file__), '..', 'data')
p_test = op.join(p_data, 'tests', 'tests_estela', 'Roi_Kwajalein')

# input data
p_estela_mat = op.join(p_test, 'kwajalein_roi_obj.mat')  # mask with estela
p_gowpoint = op.join(p_test, 'gow2_062_ 9.50_167.25.mat')  # gow point data
p_coast_mat = op.join(p_test, 'Costa.mat')  # coast 

# teslakit files
p_SLP_data = op.join(p_test, 'SLP.nc')  # extracted SLP


# --------------------------------------
# load sea polygons for mask generation
ls_sea_poly = ReadCoastMat(p_coast_mat)


# --------------------------------------
# load estela data 
xds_est = ReadEstelaMat(p_estela_mat)


# --------------------------------------
# load waves data from .mat gow file
xds_WAVES = ReadGowMat(p_gowpoint)

# calculate Fe (from GOW waves data)
hs = xds_WAVES.hs
tm = xds_WAVES.t02
Fe = np.multiply(hs**2,tm)**(1.0/3)
xds_WAVES.update({
    'Fe':(('time',), Fe)
})

# select time window and do data daily mean
xds_WAVES = xds_WAVES.sel(
    time=slice('1979-01-22','1980-12-31')
).resample(time='1D').mean()


# --------------------------------------
# load SLP (use xarray saved predictor data) 
xds_SLP_site = xr.open_dataset(p_SLP_data)

# parse data to daily average 
xds_SLP_day = xds_SLP_site.resample(time='1D').mean()

# calculate daily gradients
xds_SLP_day = spatial_gradient(xds_SLP_day, 'SLP')

# generate land mask with land polygons 
xds_SLP_day = mask_from_poly(
    xds_SLP_day, ls_sea_poly, 'mask_land')

# resample estela to site mesh
xds_est_site = xds_est.sel(
    longitude = xds_SLP_day.longitude,
    latitude = xds_SLP_day.latitude,
)
estela_D = xds_est_site.D_y1993to2012


# generate SLP mask using estela
mask_est = np.zeros(estela_D.shape)
mask_est[np.where(estela_D<1000000000)]=1

xds_SLP_day.update({
    'mask_estela':(('latitude','longitude'), mask_est)
})


# --------------------------------------
# Use a tesla-kit predictor
p_SLP_pred = op.join(p_test, 'pred_SLP')
pred = Predictor(p_SLP_pred)
pred.data = xds_SLP_day


# Calculate PCA (dynamic estela predictor)
pred.Calc_PCA_EstelaPred('SLP', estela_D)

# plot PCA EOFs
n_EOFs = 3
pred.Plot_EOFs_EstelaPred(n_EOFs, show=False)


# Calculate KMA (regression guided with WAVES data)
num_clusters = 36
alpha = 0.3  # TODO: encontrar alpha optimo?
pred.Calc_KMA_regressionguided(
    num_clusters,
    xds_WAVES, ['hs','t02','Fe'],
    alpha)
pred.Save()

# plot KMA clusters
#pred.Plot_KMArg_clusters_datamean('SLP', show=True, mask_name='mask_estela')



# --------------------------------------
# load storms, find inside circle and modify predictor KMA 
from lib.hurricanes import Extract_Circle

p_data_hurr = op.join(p_data, 'HURR')
p_hurr_noaa_fix = op.join(p_data_hurr, 'Allstorms.ibtracs_wmo.v03r10_fix.nc')

xds_wmo_fix = xr.open_dataset(p_hurr_noaa_fix)

p_lon = 178
p_lat = -17.5
r = 4

xds_storms_r, xds_inside = Extract_Circle(
    xds_wmo_fix, p_lon, p_lat, r)

storm_dates = xds_inside.inside_date.values[:]
storm_categs = xds_inside.inside_category.values[:]

# modify predictor KMA with circle storms data
pred.Mod_KMA_AddStorms(storm_dates, storm_categs)
pred.Save()

