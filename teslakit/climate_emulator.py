#!/usr/bin/env python
# -*- coding: utf-8 -*-

# common
import os
import os.path as op
import time
import pickle
from itertools import permutations

# pip
import numpy as np
import xarray as xr
from scipy.special import ndtri  # norm inv
from scipy.stats import  genextreme, spearmanr, norm
from statsmodels.distributions.empirical_distribution import ECDF
from numpy.random import choice, multivariate_normal, randint, rand

# tk
from teslakit.statistical import Empirical_ICDF
from teslakit.waves import Calculate_TWL
from teslakit.storms import GetStormCategory
from teslakit.extremes import FitGEV_KMA_Frechet, Smooth_GEV_Shape


class Climate_Emulator(object):
    'KMA - DWTs Climate Emulator'

    def __init__(self, p_base):

        # max. Total Water level for each storm data
        self.KMA_MS = None
        self.WVS_MS = None

        # extremes model params
        self.GEV_Par = None         # GEV fitting parameters
        self.GEV_Par_S = None       # GEV simulation sampled parameters
        self.sigma = None           # Pearson sigma correlation

        # chromosomes
        self.chrom = None           # chromosomes and chromosomes probs

        # parameters
        self.fams = ['sea', 'swell_1', 'swell_2']  # climate emulator waves families
        self.gev_vars_fit = [
            'sea_Hs', 'sea_Tp', 'swell_1_Hs', 'swell_1_Tp', 'swell_2_Hs', 'swell_2_Tp'
        ]

        # paths
        self.p_base = p_base
        self.p_WVS_MS = op.join(p_base, 'WVS_MaxStorm.nc')
        self.p_KMA_MS = op.join(p_base, 'KMA_MaxStorm.nc')
        self.p_chrom = op.join(p_base, 'chromosomes.nc')
        self.p_GEV_Par = op.join(p_base, 'GEV_Parameters.nc')
        self.p_GEV_Par_S = op.join(p_base, 'GEV_PSampling.nc')
        self.p_GEV_Sigma = op.join(p_base, 'GEV_SigmaCorrelation.nc')
        #self.p_report_fit = op.join(p_base, 'report_fit')
        #self.p_report_sim = op.join(p_base, 'report_sim')

        # output simulation storage paths
        self.p_sim = op.join(p_base, 'Simulation')
        self.p_sim_wvs_notcs = op.join(self.p_sim, 'WAVES_noTCs')
        self.p_sim_wvs_tcs = op.join(self.p_sim, 'WAVES_TCs')
        self.p_sim_tcs = op.join(self.p_sim, 'TCs')  # simulated TCs

    def FitExtremes(self, xds_KMA, xds_WVS_parts, xds_WVS_fams):
        '''
        GEV extremes fitting.
        Input data (waves vars series and bmus) shares time dimension

        xds_KMA - xarray.Dataset, vars: bmus (time,), cenEOFs(n_clusters,n_features)
        xds_WVS_parts - xarray.Dataset: (time,), phs, pspr, pwfrac... {0-5 partitions}
        xds_WVS_fams  - xarray.Dataset: (time,), fam_V, {fam: sea,swell_1,swell2. V: Hs,Tp,Dir}
        '''

        # get start and end dates for each storm
        lt_storm_dates = self.Calc_StormsDates(xds_KMA)

        # calculate max. TWL for each storm
        xds_max_TWL = self.Calc_StormsMaxTWL(xds_WVS_parts, lt_storm_dates)

        # select WVS_families data at storms max. TWL 
        xds_WVS_MS = xds_WVS_fams.sel(time = xds_max_TWL.time)
        xds_WVS_MS['max_TWL'] = ('time', xds_max_TWL.TWL.values[:])

        # select KMA data at storms max. TWL 
        xds_KMA_MS = xds_KMA.sel(time = xds_max_TWL.time)

        # calculate chromosomes and probabilities
        xds_chrom = self.Calc_Chromosomes(xds_KMA_MS, xds_WVS_MS)

        # GEV: Fit each wave family to a GEV distribution (KMA bmus)
        xds_GEV_Par = self.Calc_GEVParams(xds_KMA_MS, xds_WVS_MS)

        # Calculate sigma spearman for each KMA - fams chromosome
        d_sigma = self.Calc_SigmaCorrelation(
            xds_KMA_MS, xds_WVS_MS, xds_GEV_Par
        )

        # store data
        self.WVS_MS = xds_WVS_MS
        self.KMA_MS = xds_KMA_MS
        self.GEV_Par = xds_GEV_Par
        self.chrom = xds_chrom
        self.sigma = d_sigma
        self.Save()

    def Save(self):
        'Saves fitted climate emulator data'

        if not op.isdir(self.p_base): os.makedirs(self.p_base)

        # store .nc files    
        self.WVS_MS.to_netcdf(self.p_WVS_MS)
        self.KMA_MS.to_netcdf(self.p_KMA_MS)
        self.chrom.to_netcdf(self.p_chrom)
        self.GEV_Par.to_netcdf(self.p_GEV_Par)

        # store pickle
        pickle.dump(self.sigma, open(self.p_GEV_Sigma, 'wb'))

    def Load(self):
        'Loads fitted climate emulator data'

        # store .nc files    
        self.WVS_MS = xr.open_dataset(self.p_WVS_MS)
        self.KMA_MS = xr.open_dataset(self.p_KMA_MS)
        self.chrom = xr.open_dataset(self.p_chrom)
        self.GEV_Par = xr.open_dataset(self.p_GEV_Par)

        # store pickle
        self.sigma = pickle.load(open(self.p_GEV_Sigma, 'rb'))

    def StoreSim(self, p_store, ls_xdsets, code):
        'Store waves and TCs simulations (list of xr.Dataset) at p_store folder'

        if not op.isdir(p_store): os.makedirs(p_store)

        for c, xds in enumerate(ls_xdsets):
            p_nc = op.join(p_store, '{0}{1:02}.nc'.format(code, c+1))
            xds.to_netcdf(p_nc, 'w')

    def Calc_StormsDates(self, xds_KMA):
        'Returns list of tuples with each storm start and end times'

        # locate dates where KMA WT changes (bmus series)
        bmus_diff = np.diff(xds_KMA.bmus.values)
        ix_ch = np.where((bmus_diff != 0))[0]+1
        ix_ch = np.insert(ix_ch, 0,0)
        ds_ch = xds_KMA.time.values[ix_ch]  # dates where WT changes

        # list of tuples with (date start, date end) for each storm (WT window)
        dates_tup_WT = [(ds_ch[c], ds_ch[c+1]-np.timedelta64(1,'D')) for c in range(len(ds_ch)-1)]
        dates_tup_WT.append((dates_tup_WT[-1][1]+np.timedelta64(1,'D'), xds_KMA.time.values[-1]))

        return dates_tup_WT

    def Calc_StormsMaxTWL(self, xds_WVS_pts, lt_storm_dates):
        'Returns xarray.Dataset with max. TWL value and time'

        # Get TWL from waves partitions data 
        xda_TWL = Calculate_TWL(xds_WVS_pts.hs, xds_WVS_pts.tp)

        # find max TWL inside each storm 
        TWL_WT_max = []
        times_WT_max = []
        for d1, d2 in lt_storm_dates:

            # get TWL inside WT window
            wt_TWL = xda_TWL.sel(time=slice(d1,d2))[:]

            # get window maximum TWL date
            wt_max_TWL = wt_TWL.where(wt_TWL==wt_TWL.max(), drop=True).squeeze()
            max_TWL = wt_max_TWL.values
            max_date = wt_max_TWL.time.values

            # append data
            TWL_WT_max.append(max_TWL)
            times_WT_max.append(max_date)

        return xr.Dataset(
            {
                'TWL':(('time',), TWL_WT_max),
            },
            coords={'time':times_WT_max}
        )

    def Calc_GEVParams(self, xds_KMA_MS, xds_WVS_MS):
        '''
        Fits each WT (KMA.bmus) waves families data to a GEV distribtion
        Requires KMA and WVS families at storms max. TWL

        Returns xarray.Dataset with GEV shape, location and scale parameters
        '''

        vars_gev = self.gev_vars_fit
        bmus = xds_KMA_MS.bmus.values[:]
        cenEOFs = xds_KMA_MS.cenEOFs.values[:]
        n_clusters = len(xds_KMA_MS.n_clusters)

        xds_GEV_Par = xr.Dataset(
            coords={
                'n_cluster' : np.arange(n_clusters)+1,
                'parameter' : ['shape', 'location', 'scale'],
            }
        )

        # Fit each wave family var to GEV distribution (using KMA bmus)
        for vn in vars_gev:
            gp_pars = FitGEV_KMA_Frechet(bmus, n_clusters, xds_WVS_MS[vn].values)
            xds_GEV_Par[vn] = (('n_cluster', 'parameter',), gp_pars)

        return xds_GEV_Par

    def Calc_Chromosomes(self, xds_KMA_MS, xds_WVS_MS):
        '''
        Calculate chromosomes and probabilities from KMA.bmus data

        Returns xarray.Dataset vars: chrom, chrom_probs. dims: WT, wave_family
        '''

        bmus = xds_KMA_MS.bmus.values[:]
        n_clusters = len(xds_KMA_MS.n_clusters)
        fams_chrom = self.fams
        l_vc = [ '{0}_Hs'.format(x) for x in fams_chrom]

        # get chromosomes matrix
        np_vc = np.column_stack([xds_WVS_MS[vn].values for vn in l_vc])
        chrom = ChromMatrix(np_vc)

        # calculate chromosomes probabilities
        probs = np.zeros((n_clusters, chrom.shape[0]))
        for i in range(n_clusters):
            c = i+1
            pos = np.where((bmus==c))[0]

            # get variables chromosomes at cluster
            var_c = np_vc[pos,:]
            var_c[~np.isnan(var_c)] = 1
            var_c[np.isnan(var_c)] = 0

            # count chromosomes
            ucs, ccs = np.unique(var_c, return_counts=True, axis=0)
            tcs = var_c.shape[0]

            # get probs of each chromosome
            for uc, cc in zip(ucs, ccs):

                # skip all empty chromosomes
                if ~uc.any(): continue

                pc = np.where(np.all(uc == chrom, axis=1))[0][0]
                probs[i, pc] = cc / tcs

        # chromosomes dataset
        return xr.Dataset(
            {
                'chrom':(('n','wave_family',), chrom),
                'probs':(('WT','n',), probs),
            },
            coords={
                'WT':np.arange(n_clusters)+1,
                'wave_family': fams_chrom,
            }
        )

    def Calc_SigmaCorrelation(self, xds_KMA_MS, xds_WVS_MS, xds_GEV_Par):
        'Calculate Sigma Pearson correlation for each WT-chromosome combo'

        # TODO: alguna diferencia con matlab, corregir 

        bmus = xds_KMA_MS.bmus.values[:]
        cenEOFs = xds_KMA_MS.cenEOFs.values[:]
        n_clusters = len(xds_KMA_MS.n_clusters)
        wvs_fams = self.fams

        # smooth GEV shape parameter 
        d_shape = {}
        for wf in wvs_fams:
            for wv in ['Hs', 'Tp']:
                vn = '{0}_{1}'.format(wf, wv)
                sh_GEV = xds_GEV_Par.sel(parameter='shape')[vn].values[:]
                d_shape[vn] = Smooth_GEV_Shape(cenEOFs, sh_GEV)

        # Get sigma correlation for each KMA cluster 
        d_sigma = {}  # nested dict [WT][crom]
        for i in range(n_clusters):
            c = i+1
            pos = np.where((bmus==c))[0]
            d_sigma[c] = {}

            # current cluster waves
            xds_K_wvs = xds_WVS_MS.isel(time=pos)

            # get chromosomes from waves (0/1)
            var_c = np.column_stack(
                [xds_K_wvs['{0}_Hs'.format(x)].values[:] for x in wvs_fams]
            )
            var_c[~np.isnan(var_c)] = 1
            var_c[np.isnan(var_c)] = 0
            chrom = ChromMatrix(var_c)

            # get sigma for each chromosome
            for ucix, uc in enumerate(chrom):
                wt_crom = 1  # data / no data 

                # find data position for this chromosome
                p_c = np.where((var_c == uc).all(axis=1))[0]

                # if not enought data, get all chromosomes with shared 1s
                if len(p_c) < 20:
                    p1s = np.where(uc==1)[0]
                    p_c = np.where((var_c[:,p1s] == uc[p1s]).all(axis=1))[0]

                    wt_crom = 0  # data / no data 

                # select waves chrom data 
                xds_chr_wvs = xds_K_wvs.isel(time=p_c)

                # solve normal inverse GEV CDF for each active chromosome
                to_corr = np.empty((0,len(p_c)))  # append for spearman correlation
                for i_c in np.where(uc==1)[0]:

                    # get wave family chromosome variables
                    fam_n = wvs_fams[i_c]
                    vv_Hs = xds_chr_wvs['{0}_Hs'.format(fam_n)].values[:]
                    vv_Tp = xds_chr_wvs['{0}_Tp'.format(fam_n)].values[:]
                    vv_Dir = xds_chr_wvs['{0}_Dir'.format(fam_n)].values[:]

                    # GEV cdf Hs 
                    vn = '{0}_Hs'.format(fam_n)
                    sha_g = d_shape[vn][i]
                    loc_g = xds_GEV_Par.sel(parameter='location')[vn].values[i]
                    sca_g = xds_GEV_Par.sel(parameter='scale')[vn].values[i]
                    norm_Hs = genextreme.cdf(vv_Hs, -1*sha_g, loc_g, sca_g)

                    # GEV cdf Tp 
                    vn = '{0}_Tp'.format(fam_n)
                    sha_g = d_shape[vn][i]
                    loc_g = xds_GEV_Par.sel(parameter='location')[vn].values[i]
                    sca_g = xds_GEV_Par.sel(parameter='scale')[vn].values[i]
                    norm_Tp = genextreme.cdf(vv_Tp, -1*sha_g, loc_g, sca_g)

                    # ECDF dir
                    ecdf = ECDF(vv_Dir)
                    norm_Dir = ecdf(vv_Dir)

                    # normal inverse CDF 
                    u_cdf = np.column_stack([norm_Hs, norm_Tp, norm_Dir])
                    u_cdf[u_cdf>=1.0] = 0.999999
                    inv_n = ndtri(u_cdf)

                    # concatenate data for correlation
                    to_corr = np.concatenate((to_corr, inv_n.T), axis=0)

                # sigma: spearman correlation
                corr, pval = spearmanr(to_corr, axis=1)

                # store data at dict
                d_sigma[c][ucix] = {
                    'corr': corr, 'data': len(p_c), 'wt_crom': wt_crom
                }

        return d_sigma

    def Simulate_Waves(self, xds_DWT, dict_WT_TCs_wvs):
        '''
        Climate Emulator DWTs waves simulation

        xds_DWT - xarray.Dataset, vars: evbmus_sims (time,n_sim,)
        dict_WT_TCs_wvs - dict of xarray.Dataset (waves data) for TCs WTs
        '''

        # max. storm waves and KMA
        xds_KMA_MS = self.KMA_MS
        xds_WVS_MS = self.WVS_MS
        xds_chrom = self.chrom
        xds_GEV_Par = self.GEV_Par
        sigma = self.sigma

        # vars needed
        dwt_bmus_sim = xds_DWT.evbmus_sims.values[:]
        bmus = xds_KMA_MS.bmus.values[:]
        n_clusters = len(xds_KMA_MS.n_clusters)
        chrom = xds_chrom.chrom.values[:]
        chrom_probs = xds_chrom.probs.values[:]

        # iterate DWT simulations
        ls_wvs = []
        for dwt in dwt_bmus_sim.T:

            # generate waves
            wvs_sim = self.GenerateWaves(
                bmus, n_clusters, chrom, chrom_probs, sigma, xds_WVS_MS,
                xds_GEV_Par, dict_WT_TCs_wvs, dwt
            )
            ls_wvs.append(wvs_sim)

        # store simulations
        self.StoreSim(self.p_sim_wvs_notcs, ls_wvs, 'wvs_sim_noTCs_')

        return ls_wvs

    def Simulate_TCs(self, xds_DWT, dict_WT_TCs_wvs, xds_TCs_params,
                     xds_TCs_simulation, prob_change_TCs, MU_WT, TAU_WT):
        '''
        Climate Emulator DWTs TCs simulation

        xds_DWT - xarray.Dataset, vars: evbmus_sims (time,n_sim,)
        dict_WT_TCs_wvs - dict of xarray.Dataset (waves data) for TCs WTs

        xds_TCs_params - xr.Dataset. vars(storm): pressure_min
        xds_TCs_simulation - xr.Dataset. vars(storm): mu, hs, ss, tp, dir
        prob_change_TCs - cumulative probabilities of TC category change
        MU_WT, TAU_WT - intradaily hidrographs for each WT
        '''

        # max. storm waves and KMA
        xds_KMA_MS = self.KMA_MS

        # vars needed
        dwt_bmus_sim = xds_DWT.evbmus_sims.values[:]
        n_clusters = len(xds_KMA_MS.n_clusters)

        # iterate DWT simulations
        ls_tcs = []
        ls_wvs_upd = []
        for n_sim, dwt in enumerate(dwt_bmus_sim.T):

            # load waves simulation, will be modified
            p_wvs_nc = op.join(self.p_sim_wvs_notcs, 'wvs_sim_noTCs_{0:02}.nc'.format(n_sim+1))
            wvs_sim = xr.open_dataset(p_wvs_nc)

            # generate TCs
            tcs_sim, wvs_upd_sim = self.GenerateTCs(
                n_clusters, dwt,
                xds_TCs_params, xds_TCs_simulation, prob_change_TCs, MU_WT, TAU_WT,
                wvs_sim
            )
            ls_tcs.append(tcs_sim)
            ls_wvs_upd.append(wvs_upd_sim)


        # store simulations
        self.StoreSim(self.p_sim_tcs, ls_tcs, 'TCs_sim_')
        self.StoreSim(self.p_sim_wvs_tcs, ls_wvs_upd, 'wvs_sim_TCs_')

        return ls_tcs, ls_wvs_upd

    def GenerateWaves(self, bmus, n_clusters, chrom, chrom_probs, sigma,
                      xds_WVS_MS, xds_GEV_Par, TC_WVS, DWT):
        '''
        Climate Emulator DWTs waves simulation

        bmus - KMA max. storms bmus series
        n_clusters - KMA number of clusters
        chrom, chrom_probs - chromosomes and probabilities
        sigma - pearson correlation for each WT
        TC_WVS - dictionary. keys: WT, vals: xarray.Dataset TCs waves fams
        DWT - np.array with DWT bmus sim series (dims: time,)

        returns xarray.Dataset with generated waves data
        '''

        wvs_fams = self.fams

        # simulate one value for each storm 
        dwt_df = np.diff(DWT)
        ix_ch = np.where((dwt_df != 0))[0]+1
        ix_ch = np.insert(ix_ch, 0,0)
        DWT_sim = DWT[ix_ch]

        # Simulate
        sims_out = np.zeros((len(DWT_sim), 9))
        c = 0
        while c < len(DWT_sim):
            WT = DWT_sim[c]
            iwt = WT - 1

            # KMA Weather Types waves generation
            if WT <= n_clusters:

                # get random chromosome (weigthed choice)
                pr = chrom_probs[iwt] / np.sum(chrom_probs[iwt])
                ci = choice(range(chrom.shape[0]), 1, p=pr)
                crm = chrom[ci].astype(int).squeeze()

                # get sigma correlation for this WT - crm combination 
                corr = sigma[WT][int(ci)]['corr']

                mvn_m = np.zeros(corr.shape[0])
                sims = multivariate_normal(mvn_m, corr)
                prob_sim = norm.cdf(sims, 0, 1)

                # TODO: no estoy usando la GEV sampleada sino la normal (no fisher)
                # solve normal inverse CDF for each active chromosome
                ipbs = 0  # prob_sim aux. index
                sim_row = np.zeros(9)
                for i_c in np.where(crm == 1)[0]:

                    # get wave family chromosome variables
                    fam_n = wvs_fams[i_c]
                    pb_Hs = prob_sim[ipbs+0]
                    pb_Tp = prob_sim[ipbs+1]
                    pb_Dir = prob_sim[ipbs+2]
                    ipbs +=3
                    vv_Dir = xds_WVS_MS['{0}_Dir'.format(fam_n)].values[np.where((bmus==WT))]

                    # GEV ppf Hs 
                    vn = '{0}_Hs'.format(fam_n)
                    sha_g = xds_GEV_Par.sel(parameter='shape')[vn].values[iwt]
                    loc_g = xds_GEV_Par.sel(parameter='location')[vn].values[iwt]
                    sca_g = xds_GEV_Par.sel(parameter='scale')[vn].values[iwt]
                    ppf_Hs = genextreme.ppf(pb_Hs, -1*sha_g, loc_g, sca_g)

                    # GEV ppf Tp 
                    # TODO: por defecto usar GEVs, pero switch para emipircal
                    # ICDF
                    vn = '{0}_Tp'.format(fam_n)
                    sha_g = xds_GEV_Par.sel(parameter='shape')[vn].values[iwt]
                    loc_g = xds_GEV_Par.sel(parameter='location')[vn].values[iwt]
                    sca_g = xds_GEV_Par.sel(parameter='scale')[vn].values[iwt]
                    ppf_Tp = genextreme.ppf(pb_Tp, -1*sha_g, loc_g, sca_g)

                    # EICDF dir
                    # TODO: si pb_Dir se acerca a 1, da nan el EICDF... 
                    ppf_Dir = Empirical_ICDF(vv_Dir, pb_Dir)

                    # store simulation data
                    is0,is1 = wvs_fams.index(fam_n)*3, (wvs_fams.index(fam_n)+1)*3
                    sim_row[is0:is1] = [ppf_Hs, ppf_Tp, ppf_Dir]

            # TCs Weather Types waves generation
            else:

                # Get TC-WT waves fams data 
                tws = TC_WVS['{0}'.format(WT)]

                # select random state
                ri = randint(len(tws.time))
                sea_Hs = tws.sea_Hs.values[ri]
                sea_Tp = tws.sea_Tp.values[ri]
                sea_Dir = tws.sea_Dir.values[ri]
                sw1_Hs = tws.swell_1_Hs.values[ri]
                sw1_Tp = tws.swell_1_Tp.values[ri]
                sw1_Dir = tws.swell_1_Dir.values[ri]
                sw2_Hs = tws.swell_2_Hs.values[ri]
                sw2_Tp = tws.swell_2_Tp.values[ri]
                sw2_Dir = tws.swell_2_Dir.values[ri]

                sim_row = np.array([
                    sea_Hs, sea_Tp, sea_Dir,
                    sw1_Hs, sw1_Tp, sw1_Dir,
                    sw2_Hs, sw2_Tp, sw2_Dir,
                ])

            # no nans or values < 0 stored 
            if ~np.isnan(sim_row).any() and len(np.where(sim_row<0)[0])==0:
                sims_out[c] = sim_row
                c+=1

        # return generated waves 
        return xr.Dataset(
            {
                'sea_Hs':(('storm',), sims_out[:,0]),
                'sea_Tp':(('storm',), sims_out[:,1]),
                'sea_Dir':(('storm',), sims_out[:,2]),
                'swell_1_Hs':(('storm',), sims_out[:,3]),
                'swell_1_Tp':(('storm',), sims_out[:,4]),
                'swell_1_Dir':(('storm',), sims_out[:,5]),
                'swell_2_Hs':(('storm',), sims_out[:,6]),
                'swell_2_Tp':(('storm',), sims_out[:,7]),
                'swell_2_Dir':(('storm',), sims_out[:,8]),

                'DWT_sim':(('storm',), DWT_sim),
            },
        )

    def GenerateTCs(self, n_clusters, DWT,
                    TCs_params, TCs_simulation, prob_TCs, MU_WT, TAU_WT,
                    xds_wvs_sim):
        '''
        Climate Emulator DWTs TCs simulation

        n_clusters - KMA number of clusters
        DWT - np.array with DWT bmus sim series (dims: time,)

        TCs_params - xr.Dataset. vars(storm): pressure_min
        TCs_simulation - xr.Dataset. vars(storm): mu, hs, ss, tp, dir
        prob_TCs - cumulative probabilities of TC category change
        MU_WT, TAU_WT - intradaily hidrographs for each WT
        xds_wvs_sim - xr.Dataset, waves simulated without TCs (for updating)

        returns xarray.Datasets with updated Waves and simulated Tcs data
        '''

        wvs_fams = self.fams

        # simulate one value for each storm 
        dwt_df = np.diff(DWT)
        ix_ch = np.where((dwt_df != 0))[0]+1
        ix_ch = np.insert(ix_ch, 0,0)
        DWT_sim = DWT[ix_ch]

        # get simulated waves for updating
        sim_wvs = np.column_stack([
            xds_wvs_sim.sea_Hs.values[:],
            xds_wvs_sim.sea_Tp.values[:],
            xds_wvs_sim.sea_Dir.values[:],
            xds_wvs_sim.swell_1_Hs.values[:],
            xds_wvs_sim.swell_1_Tp.values[:],
            xds_wvs_sim.swell_1_Dir.values[:],
            xds_wvs_sim.swell_2_Hs.values[:],
            xds_wvs_sim.swell_2_Tp.values[:],
            xds_wvs_sim.swell_2_Dir.values[:],
        ])

        # Simulate
        sims_out = np.zeros((len(DWT_sim), 3))
        c = 0
        while c < len(DWT_sim):
            WT = DWT_sim[c]
            iwt = WT - 1

            # KMA Weather Types tcs generation
            if WT <= n_clusters:

                # get random MU,TAU from current WT
                ri = randint(len(MU_WT[iwt]))
                mu_s = MU_WT[iwt][ri]
                tau_s = TAU_WT[iwt][ri]
                ss_s = 0


            # TCs Weather Types waves generation
            else:
                # get probability of category change for this WT
                prob_t = np.append(prob_TCs[:, iwt-n_clusters], 1)

                ri = rand()
                si = np.where(prob_t >= ri)[0][0]

                if si == len(prob_t)-1:
                    # TC does not enter. random mu_s, 0.5 tau_s, 0 ss_s
                    all_MUs = np.concatenate(MU_WT)
                    ri = randint(len(all_MUs))
                    # TODO: check mu 0s, set nans (?)

                    mu_s = all_MUs[ri]
                    tau_s = 0.5
                    ss_s = 0

                else:
                    s_pmin = TCs_params.pressure_min.values[:]
                    p1, p2 = {
                        0:(1000, np.nanmax(s_pmin)+1),
                        1:(979, 1000),
                        2:(964, 979),
                        3:(944, 964),
                        4:(920, 944),
                        5:(np.nanmin(s_pmin)-1, 920),
                    }[si]

                    psi = np.where((s_pmin > p1) & (s_pmin <= p2))[0]

                    if psi.any():
                        ri = randint(len(psi))
                        mu_s = TCs_simulation.mu.values[ri]
                        ss_s = TCs_simulation.ss.values[ri]
                        tau_s = 0.5

                        # Get waves sea family from simulated TCs (num+rbf)
                        sea_Hs = TCs_simulation.hs.values[ri]
                        sea_Tp = TCs_simulation.tp.values[ri]
                        sea_Dir = TCs_simulation.dir.values[ri]

                        # update data for simulated waves (sea family)
                        sim_wvs[c, :] = [sea_Hs, sea_Tp, sea_Dir, 0, 0, 0, 0, 0, 0]

                    else:
                        # TODO: no deberia caer aqui. comentar duda
                        mu_s = 0
                        ss_s = 0
                        tau_s = 0

            sim_row = np.array([mu_s, tau_s, ss_s])

            # no nans or values < 0 stored 
            if ~np.isnan(sim_row).any() and len(np.where(sim_row<0)[0])==0:
                sims_out[c] = sim_row
                c+=1

        # generate updated waves simulation xarray.Dataset 
        xds_WVS_sim_updated = xr.Dataset(
            {
                'sea_Hs':(('storm',), sim_wvs[:,0]),
                'sea_Tp':(('storm',), sim_wvs[:,1]),
                'sea_Dir':(('storm',), sim_wvs[:,2]),
                'swell_1_Hs':(('storm',), sim_wvs[:,3]),
                'swell_1_Tp':(('storm',), sim_wvs[:,4]),
                'swell_1_Dir':(('storm',), sim_wvs[:,5]),
                'swell_2_Hs':(('storm',), sim_wvs[:,6]),
                'swell_2_Tp':(('storm',), sim_wvs[:,7]),
                'swell_2_Dir':(('storm',), sim_wvs[:,8]),

                'DWT_sim':(('storm',), DWT_sim),
            },
        )

        # generated TCs 
        xds_TCs_sim = xr.Dataset(
            {
                'mu':(('storm',), sims_out[:,0]),
                'tau':(('storm',), sims_out[:,1]),
                'ss':(('storm',), sims_out[:,2]),

                'DWT_sim':(('storm',), DWT_sim),
            },
        )

        return xds_TCs_sim, xds_WVS_sim_updated


def ChromMatrix(vs):
    'Return chromosome matrix for np.array vs (n x nvars)'

    n_cols = vs.shape[1]
    chrom = np.empty((0,n_cols), int)
    b = np.zeros(n_cols)
    for c in range(n_cols):
        b[c] = 1
        for r in set(permutations(b.tolist())):
            chrom = np.row_stack([chrom, np.array(r)])

    return chrom
