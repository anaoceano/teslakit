#!/usr/bin/env python
# -*- coding: utf-8 -*-

# basic import
import os
import os.path as op
import sys
sys.path.insert(0, op.join(op.dirname(__file__),'..','..'))

# python libs
import numpy as np
import xarray as xr

# custom libs
from teslakit.project_site import PathControl
from teslakit.climate_emulator import Climate_Emulator
from teslakit.waves import TWL_WavesFamilies, TWL_AnnualMaxima


# --------------------------------------
# Test data storage

pc = PathControl()
p_tests = pc.p_test_data
p_test = op.join(p_tests, 'ClimateEmulator', 'CE_FitExtremes')

# input
p_ce = op.join(p_test, 'ce')


# --------------------------------------
# Climate Emulator object 
CE = Climate_Emulator(p_ce)

# load previously simulated storms (without TCs)
ls_wvs_sim = CE.LoadSim(TCs=False)

for wvs_sim in ls_wvs_sim:

    # calculate TWL (waves families)
    wvs_TWL = TWL_WavesFamilies(wvs_sim)

    # calculate Annual Maxima
    wvs_TWL_AMax = TWL_AnnualMaxima(wvs_TWL)
    print(wvs_TWL_AMax)



# load previously simulated storms (with TCs)
ls_wvs_upd, ls_tcs_sim = CE.LoadSim(TCs=True)

print(ls_wvs_upd)
print()
print(ls_tcs_sim)
print()

# TODO: calculate simulated waves annual maxima (teslakit/waves.py)
# TODO: COMENTAR CON ANA/LAURA por "gow_ConciclonesRBF_pmean.mat"

