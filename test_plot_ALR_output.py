#!/usr/bin/env python
# -*- coding: utf-8 -*-

import h5py
import os.path as op
from lib.io.matlab import ReadMatfile as rmat
from lib.custom_dateutils import datevec2datetime
from lib.custom_plot import Plot_ARL_PerpYear


# data storage
p_data = '/Users/ripollcab/Projects/TESLA-kit/teslakit/data'
p_tests = op.join(p_data, 'tests_ALR', 'tests_ALR_statsmodel')


# TODO: TEST CON UN .h5 de los tests_alr_covars
#name_out = 'ALR_SM_1000iter_mk0_seas24_y300s2.h5'
#p_out = op.join(p_tests, name_out)

# load results for matlab plot 
#hf = h5py.File(p_out, 'r')
#bmus_sim = hf['bmusim'].value




# TODO: CON LOS DATOS HISTORICOS KMA_daily_42.mat
p_mat = op.join(p_tests, 'real_bmus_compare','KMA_daily_42.mat')
KMA_hist = rmat(p_mat)['KMA']
bmus_hist = KMA_hist['bmus']
dates_hist = datevec2datetime(KMA_hist['Dates'])


num_wts = 42
num_sims = 1  # TODO: los datos historicos 1 simulacion

# Plot perpetual year
Plot_ARL_PerpYear(bmus_hist, dates_hist, num_wts, num_sims)


# TODO EL OUTPUT DE ALR DEBE SER UN DATASET CON METADATA: num_wts, num_sims,
# name_covariates, value_covariates, 
