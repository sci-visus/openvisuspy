import os,copy,math

VISUS_BACKEND=os.environ.get("VISUS_BACKEND","cpp").lower()
print(f"VISUS_BACKEND={VISUS_BACKEND}")

# //////////////////////////////////////////////////////////////////////////
class BaseDataset:

	# getAlignedBox
	def getAlignedBox(self, logic_box, H, slice_dir:int=None):
		ret=copy.deepcopy(logic_box)
		pdim=self.getPointDim()
		maxh=self.getMaxResolution()
		bitmask=self.getBitmask()
		delta=[1,1,1]
		for B in range(maxh,H,-1):
			bit=ord(bitmask[B])-ord('0')
			A,B,D=ret[0][bit], ret[1][bit], delta[bit]
			D*=2
			A=int(math.floor(A/D))*D
			B=int(math.ceil (B/D))*D
			B=max(A+D,B)
			ret[0][bit] = A 
			ret[1][bit] = B
			delta[bit] = D
		
		#  force to be a slice?
		if pdim==3 and slice_dir is not None:
			offset=ret[0][slice_dir]
			ret[1][slice_dir]=offset+0
			ret[1][slice_dir]=offset+1
			delta[slice_dir]=1
		
		num_pixels=[(ret[1][I]-ret[0][I])//delta[I] for I in range(pdim)]
		return ret, delta,num_pixels

if VISUS_BACKEND=="cpp":
	from . backend_cpp import *

elif VISUS_BACKEND == 'py':
    from . backend_py import *

else:
	raise Exception("internal error, unsupported ")

