#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..'))

import numpy as np
import xarray as xr
from datetime import datetime
import pickle

# tk libs
from lib.io.matlab import ReadGowMat, ReadMatfile
from lib.intradaily import Calculate_Hydrographs
from lib.custom_dateutils import datevec2datetime


# --------------------------------------
# data storage
p_data = op.join(op.dirname(__file__), '..', 'data')
p_test = op.join(p_data, 'tests', 'tests_intradaily')

p_GOW = op.join(p_test, 'Waves_partitions', 'point1.mat')
p_KMA = op.join(p_test, 'KMA_daily_42_all.mat')

# output dictionary of hydrographs
p_dbins = op.join(p_test, 'dbins_hydrographs.pk')


# load variables from matlab to xarray.Dataset
xds_WAVES = ReadGowMat(p_GOW)

d_KMA = ReadMatfile(p_KMA)
xds_BMUS = xr.Dataset(
    {
        'bmus': (('time',), d_KMA['KMA']['CorrectedBmus'])
    },
    coords = {
        'time': datevec2datetime(d_KMA['KMA']['Dates']),
    }
)


# --------------------------------------
# Calculate hydrographs 
dict_bins = Calculate_Hydrographs(xds_BMUS, xds_WAVES)

# TODO: add hydrograph plots lib/plotting/intradaily

# store output
pickle.dump(dict_bins, open(p_dbins,'wb'))
#pickle.load(open(p_dbins,'rb'))  # for loading

