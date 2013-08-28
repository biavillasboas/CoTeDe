""" Apply Quality Control of CTD profiles
"""

import pkg_resources
from datetime import datetime

import numpy as np
from numpy import ma

from cotede.utils import get_depth_from_DAP
from cotede.utils import woa_profile_from_dap

class ProfileQC(object):
    """ Quality Control of a CTD profile
    """
    def __init__(self, input, cfg={}):
        """
            Input: dictionary with data.
                - pressure[\d]:
                - temperature[\d]: 
                - salinity[\d]: 

            cfg: config file with thresholds

            =======================
            - Must have a log system
            - Probably accept incomplete cfg. If some threshold is
                not defined, take the default value.
            - Is the best return another dictionary?
        """

        self.input = input
        self.load_cfg(cfg)
        self.flags = {}

        if 'valid_datetime' in self.cfg['main']:
            self.flags['valid_datetime'] = \
                    type(self.input.attributes['datetime'])==datetime
        if 'at_sea' in self.cfg['main']:
            lon = self.input.attributes['longitude']
            lat = self.input.attributes['latitude']
            if 'url' in self.cfg['main']['at_sea']:
                depth = get_depth_from_DAP(np.array([lat]), 
                        np.array([lon]),
                        url=self.cfg['main']['at_sea']['url'])
                #flag[depth<0] = True
                #flag[depth>0] = False
                #self.flags['at_sea'] = flag
                self.flags['at_sea'] = depth[0]<0

        # Must have a better way to do this!
        import re
        for v in self.input.keys():
            c = re.sub('2$','', v)
            if c in self.cfg.keys():
                self.test_var(v, self.cfg[c])

    def load_cfg(self, cfg):
        """ Load the user's config and the default values

            Need to think better what do I want here. The user
              should be able to choose which variables to evaluate.

            How to handle conflicts between user's cfg and default?
        """
        #defaults = pkg_resources.resource_listdir(__name__, 'defaults')
        self.cfg = eval(pkg_resources.resource_string(__name__, 'defaults'))
        for k in cfg:
            self.cfg[k] = cfg[k]

    def test_var(self, v, cfg):

        self.flags[v] = {}
        if 'global_range' in cfg:
            f = (self.input[v] >= cfg['global_range']['minval']) & (self.input[v] <= cfg['global_range']['maxval'])
            self.flags[v]['global_range'] = f

        if 'gradient' in cfg:
            threshold = cfg['gradient']
            x = self.input[v]
            g = ma.masked_all(x.shape)
            g[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:])/2.0)
            flag = ma.masked_all(x.shape, dtype=np.bool)
            flag[np.nonzero(g>threshold)] = False
            flag[np.nonzero(g<=threshold)] = True
            self.flags[v]['gradient'] = flag

        if 'spike' in cfg:
            threshold = cfg['spike']
            x = self.input[v]
            s = ma.masked_all(x.shape)
            s[1:-1] = np.abs(x[1:-1] - (x[:-2] + x[2:])/2.0) - np.abs((x[2:] - x[:-2])/2.0)
            flag = ma.masked_all(x.shape, dtype=np.bool)
            flag[np.nonzero(s>threshold)] = False
            flag[np.nonzero(s<=threshold)] = True
            self.flags[v]['spike'] = flag

        if 'digit_roll_over' in cfg:
            threshold = cfg['digit_roll_over']
            x = self.input[v]
            d = ma.masked_all(x.shape)
            step = ma.masked_all(x.shape, dtype=np.float)
            step[1:] = ma.absolute(ma.diff(x))
            flag = ma.masked_all(x.shape, dtype=np.bool)
            flag[ma.absolute(step)>threshold] = False
            flag[ma.absolute(step)<=threshold] = True
            self.flags[v]['digit_roll_over'] = flag

        if 'woa_comparison' in cfg:
            try:
                woa_an, woa_sd = woa_profile_from_dap(v, 
                    int(self.input.attributes['datetime'].strftime('%j')),
                    self.input.attributes['latitude'], 
                    self.input.attributes['longitude'], 
                    self.input['pressure'])
                woa_anom = (self.input[v] - woa_an) / woa_sd
                self.flags[v]['woa_comparison'] = \
                    woa_anom < 3
            except:
                print "Couldn't make woa_comparison of %s" % v

class ProfileQCed(ProfileQC):
    """
    """
    def __init__(self, input, cfg={}):
        """
        """
        super(ProfileQCed, self).__init__(input, cfg)
        self.name = 'ProfileQCed'

    def keys(self):
        """ Return the available keys in self.data
        """
        return self.input.keys()

    def __getitem__(self, key):
        """ Return the key array from self.data
        """
        if key not in self.flags.keys():
            return self.input[key]
        else:
            f = ma.array([self.flags[key][f] for f in self.flags[key]]).T
            mask = self.input[key].mask | (~f).any(axis=1)
            return ma.masked_array(self.input[key].data, mask)

        raise KeyError('%s not found' % key)
