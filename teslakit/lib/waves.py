#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import xarray as xr

np.warnings.filterwarnings('ignore')


def GetDistribution(xds_wps, swell_sectors):
    '''
    Separates wave partitions (0-5) into families.
    Default: sea, swl1, swl2

    xds_wps (waves partitionss):
        (time,), phs, pspr, pwfrac... {0-5 partitions}

    sectors: list of degrees to cut wave energy [(a1, a2), (a2, a3), (a3, a1)]
    '''

    # fix data
    hs_fix_data = 50
    for i in range(6):
        phs = xds_wps['phs{0}'.format(i)].values
        p_fix = np.where(phs >= hs_fix_data)[0]

        # fix data
        xds_wps['phs{0}'.format(i)][p_fix] = np.nan
        xds_wps['ptp{0}'.format(i)][p_fix] = np.nan
        xds_wps['pdir{0}'.format(i)][p_fix] = np.nan

    # sea (partition 0)
    sea_Hs = xds_wps['phs0'].values
    sea_Tp = xds_wps['ptp0'].values
    sea_Dir = xds_wps['pdir0'].values
    time = xds_wps['time'].values

    # concatenate energy groups 
    cat_hs = np.column_stack(
        (xds_wps.phs1.values,
        xds_wps.phs2.values,
        xds_wps.phs3.values,
        xds_wps.phs4.values,
        xds_wps.phs5.values )
    )
    cat_tp = np.column_stack(
        (xds_wps.ptp1.values,
        xds_wps.ptp2.values,
        xds_wps.ptp3.values,
        xds_wps.ptp4.values,
        xds_wps.ptp5.values )
    )
    cat_dir = np.column_stack(
        (xds_wps.pdir1.values,
        xds_wps.pdir2.values,
        xds_wps.pdir3.values,
        xds_wps.pdir4.values,
        xds_wps.pdir5.values )
    )


    # prepare output array
    xds_parts = xr.Dataset({
        'sea_Hs':('time',sea_Hs),
        'sea_Tp':('time',sea_Tp),
        'sea_Dir':('time',sea_Dir)
    },
        coords = {'time':time}
    )

    # solve sectors
    c = 1
    for s_ini, s_end in swell_sectors:
        if s_ini < s_end:
            p_sw = np.where((cat_dir <= s_end) & (cat_dir > s_ini))
        else:
            p_sw = np.where((cat_dir <= s_end) | (cat_dir > s_ini))

        # get data inside sector
        sect_dir = np.zeros(cat_dir.shape)*np.nan
        sect_hs = np.zeros(cat_dir.shape)*np.nan
        sect_tp = np.zeros(cat_dir.shape)*np.nan

        sect_dir[p_sw] = cat_dir[p_sw]
        sect_hs[p_sw] = cat_hs[p_sw]
        sect_tp[p_sw] = cat_tp[p_sw]

        # calculate swell Hs, Tp, Dir
        swell_Hs = np.sqrt(np.nansum(np.power(sect_hs,2), axis=1))
        swell_Tp = np.sqrt(
            np.nansum(np.power(sect_hs,2), axis=1) /
            np.nansum(np.power(sect_hs,2)/np.power(sect_tp,2), axis=1)
        )
        swell_Dir = np.arctan2(
            np.nansum(np.power(sect_hs,2) * sect_tp * np.sin(sect_dir*np.pi/180), axis=1),
            np.nansum(np.power(sect_hs,2) * sect_tp * np.cos(sect_dir*np.pi/180), axis=1)
        )
        # TODO: la formula pierde sentido cuando solo hay 1 familia?
        # si es asi sacar posiciones /valores sect_dir y aplicar 
        swell_Dir[np.where((swell_Dir<0))]=(swell_Dir[np.where((swell_Dir<0))]+2*np.pi)*180/np.pi

        # TODO out of bound correction
        swell_Dir[np.where((swell_Dir>360))] = swell_Dir[np.where((swell_Dir>360))]-360
        swell_Dir[np.where((swell_Dir<0))] = swell_Dir[np.where((swell_Dir<0))]+360

        # append data to partitons dataset
        xds_parts['swell_{0}_Hs'.format(c)] = ('time', swell_Hs)
        xds_parts['swell_{0}_Tp'.format(c)] = ('time', swell_Tp)
        xds_parts['swell_{0}_Dir'.format(c)] = ('time', swell_Dir)
        c+=1

    return xds_parts

