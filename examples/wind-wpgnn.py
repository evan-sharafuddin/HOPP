# HOPP with WPGNN solver
# first step in trying to use WPGNN solver to optimize HOPP wind plant layouts

from hopp.simulation import HoppInterface

hi = HoppInterface("examples/inputs/wind-wpgnn.yaml")
hi.simulate(25)