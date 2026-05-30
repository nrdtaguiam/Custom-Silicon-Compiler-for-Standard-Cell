import numpy as np

data = np.loadtxt("vtc.dat")

Vin = data[:, 0]
Vout = data[:, 1]

# derivative
dVout_dVin = np.gradient(Vout, Vin)

# find slope = -1 crossings
idx = np.where(np.diff(np.sign(dVout_dVin + 1)))[0]

if len(idx) < 2:
    raise ValueError("VIL / VIH not found")

VIL = Vin[idx[0]]
VIH = Vin[idx[-1]]

print(f"VIL = {VIL:.4f} V")
print(f"VIH = {VIH:.4f} V")
