from __future__ import print_function

import time
import os
import numpy as np

from hexrd import imageseries
from hexrd.imageseries.process import ProcessedImageSeries




class ProcessedDexelaIMS(ProcessedImageSeries):

    ADDROW = 'add-row'
    ADDCOL = 'add-column'

    def __init__(self, imser, oplist, **kwargs):
        super(ProcessedDexelaIMS, self).__init__(imser, oplist, **kwargs)
        self.addop(self.ADDROW, self._addrow)
        self.addop(self.ADDCOL, self._addcol)

    def _addrow(self, img, k):
        """insert row into position k"""
        shp = img.shape
        pimg = np.insert(img, k, 0, axis=0)
        if k==0:
            pimg[0] = pimg[1]
        elif k==shp[0]:
            pimg[k] = pimg[k-1]
        else: # in middle
            pimg[k] = (pimg[k-1] + pimg[k+1])/2

        return pimg

    def _addcol(self, img, k):
        """insert row into position k"""
        shp = img.shape
        pimg = np.insert(img, k, 0, axis=1)
        if k==0:
            pimg[:,0] = pimg[:,1]
        elif k==shp[0]:
            pimg[:,k] = pimg[:,k-1]
        else: # in middle
            pimg[:,k] = (pimg[:,k-1] + pimg[:,k+1])/2

        return pimg


DexelaIMS=ProcessedDexelaIMS

class PP_Dexela(object):
    """PP_Dexela"""
    PROCFMT = 'frame-cache'
    RAWFMT = 'hdf5'
    RAWPATH = '/imageseries'
    DARKPCTILE = 50

    def __init__(self,
                 fname, omw, panel_opts, panel_id,
                 frame_start=0, raw_format='hdf5',dark=None):
        """Constructor for PP_Dexela"""
        self._panel_id = panel_id
        self.fname = fname
        self.omwedges = omw
        self.panel_opts = panel_opts
        self.frame_start = frame_start
        #self.use_frame_list = (self.frame_start > 0)
        if raw_format.lower() == 'hdf5':
            self.raw = imageseries.open(
                self.fname, self.RAWFMT, path=self.RAWPATH
                )
        else:
            self.raw = imageseries.open(self.fname, raw_format.lower())
        self._dark = dark

        self.use_frame_list = (self.nframes != len(self.raw))#Framelist fix, DCP 6/18/18
        print(
            'On Init:\n\t%s, %d frames, %d omw, %d total'
            % (self.fname, self.nframes, self.omwedges.nframes, len(self.raw))
        )

    @property
    def panel_id(self):
        return self._panel_id

    @property
    def oplist(self):
        return [('dark', self.dark)]+self.panel_opts

    @property
    def framelist(self):
        return range(self.frame_start, self.nframes + self.frame_start)

    #
    # ============================== API
    #
    @property
    def nframes(self):
        return self.omwedges.nframes

    @property
    def omegas(self):
        return self.omwedges.omegas

    def processed(self):
        kw = {}
        if self.use_frame_list:
            kw = dict(frame_list=self.framelist)
        return DexelaIMS(self.raw, self.oplist, **kw)

    @property
    def dark(self, nframes=100):
        """build and return dark image"""
        if self._dark is None:
            usenframes = min(nframes, self.nframes)
            print(
                "building dark images using %s frames (may take a while)..."
                % usenframes
            )
            start = time.time()
#            self._dark = imageseries.stats.percentile(
#                    self.raw, self.DARKPCTILE, nframes=usenframes
#            )
            self._dark = imageseries.stats.median(
                    self.raw, nframes=usenframes
            )#changed to median by DCP 11/18/17
            elapsed = (time.time() - start)
            print(
                "done building background (dark) image: " +
                "elapsed time is %f seconds" % elapsed
            )

        return self._dark

    def save_processed(self, name, threshold, output_dir=None):
        if output_dir is None:
            output_dir = os.getcwd()
        else:
            os.mkdir(output_dir)

        # add omegas
        pims = self.processed()
        metad = pims.metadata
        metad['omega'] = self.omegas
        metad['panel_id'] = self.panel_id
        cache = '%s-cachefile.npz' % name
        imageseries.write(pims, "dummy", self.PROCFMT,
                          style="npz",
                          threshold=threshold,
                          cache_file=cache)
    pass  # end class
