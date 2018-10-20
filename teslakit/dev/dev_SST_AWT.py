#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

# python libs
import xarray as xr
from datetime import datetime, timedelta
import numpy as np

# tk libs
from lib.objs.tkpaths import Site
from lib.KMA import KMA_simple
from lib.statistical import Persistences, ksdensity_CDF
from lib.plotting.EOFs import Plot_EOFs_latavg as PlotEOFs
from lib.PCA import CalcPCA_latavg as CalcPCA
from lib.PCA import CalcRunningMean
from lib.objs.alr_wrapper import ALR_WRP


# --------------------------------------
# Site paths and parameters
site = Site('KWAJALEIN')
site.Summary()

# input files
p_SST = site.pc.DB.sst.hist_pacific  # SST Pacific area

# output files
p_export_figs = site.pc.site.exp.sst
p_sst_PCA = site.pc.site.sst.PCA
p_sst_KMA = site.pc.site.sst.KMA

# PCA dates parameters
pred_name = 'SST'
y1 = site.params.SST_AWT.pca_year_ini
yN = site.params.SST_AWT.pca_year_end
m1 = site.params.SST_AWT.pca_month_ini
mN = site.params.SST_AWT.pca_month_end

# Simulation dates (ALR)
year_sim1 = site.params.SIMULATION.date_ini.split('-')[0]
year_sim2 = site.params.SIMULATION.date_end.split('-')[0]


# --------------------------------------
# load SST predictor from database
xds_pred = xr.open_dataset(p_SST)


# --------------------------------------
# Calculate running average
print('\nCalculating {0} running average... '.format(pred_name))
xds_pred = CalcRunningMean(xds_pred, pred_name)

# Principal Components Analysis
print('\nPrincipal Component Analysis (latitude average)...')
xds_PCA = CalcPCA(xds_pred, pred_name, y1, yN, m1, mN)

# plot EOFs
n_plot = 3
p_export = op.join(p_export_figs, 'latavg_EOFs')  # if only show: None
PlotEOFs(xds_PCA, n_plot, p_export)


# --------------------------------------
# KMA Classification 
num_clusters = 6
repres = 0.95

print('\nKMA Classification...')
xds_AWT = KMA_simple(
    xds_PCA, num_clusters, repres)

# add yearly time data to xds_AWT
time_yearly = [datetime(x,1,1) for x in range(y1,yN+1)]
xds_AWT['time']=(('n_pcacomp'), time_yearly)

# store AWTs and PCs
xds_PCA.to_netcdf(p_sst_PCA,'w')  # store SST PCA data 
xds_AWT.to_netcdf(p_sst_KMA,'w')  # store SST KMA data 
print('\n{0} PCA and KMA stored at:\n{1}\n{2}'.format(
    pred_name, p_sst_PCA, p_sst_KMA))

# --------------------------------------
# Get more data from xds_AWT
kma_order = xds_AWT.order.values
kma_labels = xds_AWT.bmus.values


# Get bmus Persistences
# TODO: ver como guardar esta info / donde se usa?
d_pers_bmus = Persistences(xds_AWT.bmus.values)

# first 3 PCs
PCs = xds_AWT.PCs.values
variance = xds_AWT.variance.values
PC1 = np.divide(PCs[:,0], np.sqrt(variance[0]))
PC2 = np.divide(PCs[:,1], np.sqrt(variance[1]))
PC3 = np.divide(PCs[:,2], np.sqrt(variance[2]))

# TODO: PREGUNTAR ANA: entonces PC_rnd no depende de ALR output
# TODO generate copula for each WT
for i in range(num_clusters):

    # getting copula number from plotting order
    num = kma_order[i]

    # find all the best match units equal
    ind = np.where(kma_labels == num)[:]

    # transfom data using kernel estimator
    print PC1[ind]
    cdf_PC1 = ksdensity_CDF(PC1[ind])
    cdf_PC2 = ksdensity_CDF(PC2[ind])
    cdf_PC3 = ksdensity_CDF(PC3[ind])
    U = np.column_stack((cdf_PC1.T, cdf_PC2.T, cdf_PC3.T))


    # TODO COPULAFIT. fit u to a student t copula. leer la web que compara
    #  lib incompleta: https://github.com/stochasticresearch/copula-py/blob/master/copulafit.py
    #  lib con buena pinta: https://pypi.org/project/copulalib/


    # TODO COPULARND para crear USIMULADO

    # TODO: KS DENSITY ICDF PARA CREAR PC123_RND SIMULATODS

    # TODO: USAR NUM PARA GUARDAR LOS RESULTADOS




# --------------------------------------
# Autoregressive Logistic Regression
xds_bmus_fit = xr.Dataset(
    {
        'bmus':(('time',), xds_AWT.bmus),
    },
    coords = {'time': xds_AWT.time.values}
).bmus

num_wts = 10
ALRW = ALR_WRP(xds_bmus_fit, num_wts)

# ALR terms
d_terms_settings = {
    'mk_order'  : 1,
    'constant' : True,
    'long_term' : False,
    'seasonality': (False, []),
}


ALRW.SetFittingTerms(d_terms_settings)

# ALR model fitting
ALRW.FitModel()

# ALR model simulations 
sim_num = 10

dates_sim = [
    datetime(x,1,1) for x in range(year_sim1,year_sim2+1)]

xds_ALR = ALRW.Simulate(sim_num, dates_sim)

# TODO: GUARDAR RESULTADOS
print xds_ALR

