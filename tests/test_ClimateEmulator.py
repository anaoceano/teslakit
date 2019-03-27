#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

# python libs
import xarray as xr
import numpy as np

# custom libs
from lib.io.matlab import ReadMatfile as rmf
from lib.custom_dateutils import DateConverter_Mat2Py as d2d
from lib.climate_emulator import Climate_Emulator


# --------------------------------------
# files
p_data = op.join(op.dirname(__file__),'..','data')
p_data = op.join(p_data, 'tests', 'test_ExtremesGEV')

p_ce = op.join(p_data, 'ce_obj')


# --------------------------------------
# Load test data (original matlab files)

# waves and KMA MaxStorm
xds_WVS_MaxStorm = xr.open_dataset(op.join(p_data, 'xds_WT_wvs_fam_noTCs.nc'))
xds_KMA_MaxStorm = xr.open_dataset(op.join(p_data, 'xds_WT_KMA.nc'))

# TODO: actualizar input a wvs_pts, wvs_fms y kma sin modificar


# DWTs (Daily Weather Types simulated using ALR)
p_DWTs = op.join(p_data, 'Nico_Montecarlo', 'DWT_1000years_mjo_awt_v2.mat')
dm_DWTs = rmf(p_DWTs)
daily_WT = dm_DWTs['bmusim'].T
#dates_DWT = dm_DWTs['datesim']  # TODO: necesario? 



# TCs simulated with numerical and RBFs (TCs params, and TCs num/RBF output)
p_TCs = op.join(
    p_data, 'Nico_Montecarlo', 'Reconstructed_waves_MULTIVARIATE_Pmean.mat'
)
dm_TCs = rmf(p_TCs)

TCs_params = dm_TCs['Param']  # TCs parameters: pressure_mean, pressure_min...
TCs_output = dm_TCs['Results']  # TCs numerical output:  Hs, Tp, Dir, mu, SS

xds_TCs = xr.Dataset(
    {
        'pressure_min':(('storm'), TCs_params[:,0]),
        'hs':(('storm'), TCs_output[:,0]),
        'tp':(('storm'), TCs_output[:,1]),
        'dir':(('storm'), TCs_output[:,4]),
        'mu':(('storm'), TCs_output[:,5]),
        'ss':(('storm'), TCs_output[:,2]),
    },
    coords = {
        'storm':(('storm'), np.arange(TCs_params.shape[0]))
    },
)

# MU TAU intradaily hydrographs for each WT (36)
p_MUTAU = op.join(p_data, 'Nico_Montecarlo', 'MU_TAU_36WT.mat')
dm_MUTAU = rmf(p_MUTAU)
MU_WT = dm_MUTAU['MU_WT']
TAU_WT = dm_MUTAU['TAU_WT']

# TCs probs change
p_probsTCs = op.join(p_data, 'Nico_Montecarlo', 'Probabilities_Historical.mat')
pchange_TCs = rmf(p_probsTCs)['p_sint']



# get WTs37,42 from matlab file
p_WTTCs = op.join(p_data, 'Nico_Montecarlo', 'KWA_waves_2PART_TCs_nan.mat')
dm_WTTCs = rmf(p_WTTCs)

# Load TCs-window waves-families data by category
d_WTTCs = {}
for i in range(6):

    k = 'wt{0}'.format(i+1+36)
    sd = dm_WTTCs[k]

    d_WTTCs['{0}'.format(i+1+36)] = xr.Dataset(
        {
            'sea_Hs':(('time',), sd['seaHs']),
            'sea_Dir':(('time',), sd['seaDir']),
            'sea_Tp':(('time',), sd['seaTp']),
            'swell_1_Hs':(('time',), sd['swl1Hs']),
            'swell_1_Dir':(('time',), sd['swl1Dir']),
            'swell_1_Tp':(('time',), sd['swl1Tp']),
            'swell_2_Hs':(('time',), sd['swl2Hs']),
            'swell_2_Dir':(('time',), sd['swl2Dir']),
            'swell_2_Tp':(('time',), sd['swl2Tp']),
        }
    )



# --------------------------------------
# Climate Emulator extremes model fitting

# climate emulator object
CE = Climate_Emulator(p_ce)

# Waves and KMA bmus data share time dimension
xds_WVS_fam = xds_WVS_fam.sel(time=xds_KMA.time)
xds_WVS_pts = xds_WVS_pts.sel(time=xds_KMA.time)

# Fit extremes model
CE.FitExtremes(xds_KMA, xds_WVS_pts, xds_WVS_fam)


# Simulate DWTs without TCs 
xds_SIM = CE.Simulate(xds_DWT, d_WTTCs)

# TODO: ACTUALIZAR INPUT Y SIMULATE CON TCS ACTIVADO

