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
from lib.io.matlab import ReadGowMat, ReadCoastMat, ReadEstelaMat
from lib.io.cfs import ReadSLP
from lib.predictor import spatial_gradient, mask_from_poly

# data storage
p_data = op.join(op.dirname(__file__),'..','data')
p_test = op.join(p_data, 'tests_estela', 'Roi_Kwajalein')

p_estela_mat = op.join(p_test, 'kwajalein_roi_obj.mat')         # mask with estela
p_pred_SLP = op.join(p_data,'tests_estela','CFS','prmsl')   # SLP predictor
p_gowpoint = op.join(p_test, 'gow2_062_ 9.50_167.25.mat')   # gow point data
p_coast_mat = op.join(p_test, 'Costa.mat')                      # coast 

p_results = op.join(p_test, 'out_KWAJALEIN')

p_SLP_save = op.join(p_test, 'SLP.nc')


# --------------------------------------
# load sea polygons for mask generation
ls_sea_poly = ReadCoastMat(p_coast_mat)


# --------------------------------------
# load estela data 
xds_est = ReadEstelaMat(p_estela_mat)







# --------------------------------------
# load waves data from .mat gow file
#xds_gow = ReadGowMat(p_gowpoint)


# --------------------------------------
# load predictor data (we use SLP and SLP gradients)
#xds_SLP = ReadSLP(p_pred_SLP)
#xds_SLP.rename({'PRMSL_L101':'SLP'}, inplace=True)
# after reading from original files, save using xarray
#xds_SLP.to_netcdf(p_SLP_save)

# load and use xarray saved data (faster)
xds_SLP = xr.open_dataset(p_SLP_save)


# site coordinates 
lat1 = 60.5
lat2 = 0
lon1 = 115
lon2 = 280

# cut data and resample to 2º lon,lat
xds_SLP_site = xds_SLP.sel(
    latitude = slice(lat1, lat2, 4),
    longitude = slice(lon1, lon2, 4),
)

# parse data to daily average 
xds_SLP_day = xds_SLP_site.resample(time='1D').mean()

# calculate daily gradients
xds_SLP_day = spatial_gradient(xds_SLP_day, 'SLP')

# generate land mask with land polygons 
xds_SLP_day = mask_from_poly(xds_SLP_day, ls_sea_poly)
xds_SLP_day.rename({'mask':'mask_land'}, inplace=True)


# resample estela to site mesh
xds_est_site = xds_est.sel(
    longitude = xds_SLP_day.longitude,
    latitude = xds_SLP_day.latitude,
)

# generate mask using estela
mask_est = np.zeros(xds_est_site.D_y1993to2012.shape)
mask_est[np.where(xds_est_site.D_y1993to2012<1000000000)]=1

xds_SLP_day.update({
    'mask_estela':(('latitude','longitude'), mask_est)
})

# test estela and coast masks
#test = xds_SLP_day.SLP.isel(time=0).where(
#    (xds_SLP_day.mask_estela==1) & (xds_SLP_day.mask_land!=1)
#)
#test.plot()
#plt.show()


# TODO: continuar con PCA estela predictor 



