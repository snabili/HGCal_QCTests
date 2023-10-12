import ROOT as rt

from scipy.optimize import curve_fit
# scipy packages; to be used later
from scipy.interpolate import make_interp_spline
from scipy.interpolate import interp1d
from scipy.interpolate import make_interp_spline, BSpline
import numpy as np
import matplotlib.pyplot as plt
#common packages
import os, os.path as osp, glob, pickle, logging, warnings, json, math, re
from time import strftime
import common as com

# pull argument; add more options later
infile  = com.pull_arg('--infile', type=str, help='input root file from measurement').infile
outfile = com.pull_arg('--outfile',    type=str, help='output SPS plot with multi-gaussian fit').outfile

#read measured root file
f=rt.TFile(infile)
hgcroc = f.Get("unpacker_data/hgcroc")
Bins=50
h = rt.TH1F("h","h", Bins, 330, 440)
hgcroc.Draw("adc>>h","channel == 28 && half == 0")


# find number of peaks, xpoisition, height
# for now sigma --> for now manual
npeaks = 30
s = rt.TSpectrum(2*npeaks);
nfound = s.Search(h,1,"",0.01);
print(f"Found {nfound:d} candidate peaks to fit")

npeaks = 0
xpeaks = s.GetPositionX()
xpos = []
for i in range(nfound):
  xpos.append(round(xpeaks[i],1))


print(f"1st center-of-peaks: {min(xpos)}")
par = np.ones(nfound*3)
for p in range(nfound):
   xp = xpos[p]
   bin = h.GetXaxis().FindBin(xp)
   yp = h.GetBinContent(bin)
   par[3*p] = xp #floating initial values does not give uniform gain; 10% variations 
   '''par[3*p] = min(xpos) + p * 10 #fixed the peak center as the initial value
   bin = h.GetXaxis().FindBin(par[3*p])
   yp = h.GetBinContent(bin)'''
   par[3*p+1] = yp
   par[3*p+2] = 2
   npeaks+=1

# start to do the actual fit with scipy
# histogram --> numpy array
x = np.linspace(h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax()-h.GetXaxis().GetBinWidth(1), num=h.GetNbinsX())
y = [h.GetBinContent(i) for i in range(h.GetNbinsX())]

def func(x, *params):
    y = np.zeros_like(x)
    for i in range(0, len(params), 3):
        ctr = params[i]
        amp = params[i+1]
        wid = params[i+2]
        y = y + amp * np.exp( -((x - ctr)/wid)**2)
    return y

#using scipy package to fit peaks to multi-gaussian
guess = par
popt, pcov = curve_fit(func,x,y,p0=par)
fit = func(x, *popt)

#printing the gain
sort_cntr = sorted([popt[3*i] for i in range(npeaks)]) #sorting peaks centers
gain = [np.abs(sort_cntr[i+1]-sort_cntr[i]) for i in range(npeaks-1)]
print([ "{:0.1f}".format(x) for x in gain])


#plotting
plt.hist(x, bins=50,weights=y, histtype='step',label='SPS plot')
plt.plot(x,fit,'r-',label='Gaussian Fit')
plt.title('SinglePhotonSpectrum plot')
plt.legend()
plt.xlabel('ADC count')
plt.ylabel('A.U.')
plt.grid(True)
#plt.show()
plt.savefig('sps.png')
